"""OpenAI 兼容 Adapter。

支持所有 OpenAI API 兼容端点：
  - OpenAI 官方
  - Moonshot (Kimi)
  - DeepSeek
  - Azure OpenAI（兼容模式）
  - vLLM / Ollama（兼容模式）
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from .base import BaseLLMAdapter, HealthStatus, LLMResponse, TokenUsage
from .exceptions import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMContentFilterError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from .retry import with_llm_retry


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI 兼容 Adapter。

    使用原生 HTTP 调用（httpx），不依赖 openai SDK，
    保持与其他 adapter 的实现风格一致。
    """

    def __init__(
        self,
        provider_name: str = "openai",
        *,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "gpt-4o",
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            **kwargs,
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------

    @with_llm_retry(max_retries=3, backoff_initial=1.0)
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]

        t0 = time.perf_counter()
        try:
            resp = self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"{self.provider_name} 请求超时", provider=self.provider_name
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_from_http_error(exc)
        except Exception as exc:
            raise LLMAdapterError(
                f"{self.provider_name} 请求失败: {exc}", provider=self.provider_name
            ) from exc

        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=payload["model"],
            usage=token_usage,
            latency_ms=latency_ms,
            meta={"finish_reason": choice.get("finish_reason")},
            raw_response=data,
        )

    # ------------------------------------------------------------------
    # embed
    # ------------------------------------------------------------------

    @with_llm_retry(max_retries=3, backoff_initial=1.0)
    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        payload = {
            "model": kwargs.get("model") or getattr(self.config, "embed_model", "text-embedding-3-small"),
            "input": texts,
        }
        if "dimensions" in kwargs:
            payload["dimensions"] = kwargs["dimensions"]

        try:
            resp = self._client.post("/embeddings", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"{self.provider_name} embed 超时", provider=self.provider_name
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_from_http_error(exc)

        data = resp.json()
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    # ------------------------------------------------------------------
    # health check
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        try:
            resp = self._client.get("/models", timeout=5.0)
            if resp.status_code == 200:
                return HealthStatus.HEALTHY
            if resp.status_code in (502, 503, 504):
                return HealthStatus.UNHEALTHY
            return HealthStatus.DEGRADED
        except httpx.TimeoutException:
            return HealthStatus.DEGRADED
        except Exception:
            return HealthStatus.UNHEALTHY

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _raise_from_http_error(self, exc: httpx.HTTPStatusError) -> None:
        """将 HTTP 错误翻译为统一异常。"""
        status = exc.response.status_code
        try:
            body = exc.response.json()
            msg = body.get("error", {}).get("message", str(exc))
            code = body.get("error", {}).get("code", "")
        except Exception:
            msg = str(exc)
            code = ""

        if status == 401:
            raise LLMAuthenticationError(msg, provider=self.provider_name, code=code) from exc
        if status == 429:
            raise LLMRateLimitError(msg, provider=self.provider_name, code=code) from exc
        if status == 400:
            raise LLMBadRequestError(msg, provider=self.provider_name, code=code) from exc
        if status == 403:
            raise LLMContentFilterError(msg, provider=self.provider_name, code=code) from exc
        if status >= 500:
            raise LLMServiceUnavailableError(msg, provider=self.provider_name, code=code) from exc
        raise LLMAdapterError(msg, provider=self.provider_name, code=code) from exc

    # ------------------------------------------------------------------
    # generate_stream
    # ------------------------------------------------------------------

    def generate_stream(self, messages: list[dict[str, str]], **kwargs: Any):
        """流式生成（OpenAI SSE 格式）。

        Yields:
            LLMResponse: 每个片段包装为 LLMResponse，usage 在最终片段中填充。
        """
        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "stream": True,
        }
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]

        with self._client.stream("POST", "/chat/completions", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError(
                    f"{self.provider_name} 流式请求超时", provider=self.provider_name
                ) from exc
            except httpx.HTTPStatusError as exc:
                self._raise_from_http_error(exc)

            import json as _json

            full_content = ""
            usage = None
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    event = _json.loads(data)
                except _json.JSONDecodeError:
                    continue

                # 某些 provider 会在最后一个 chunk 中返回 usage
                if "usage" in event and event["usage"]:
                    u = event["usage"]
                    usage = TokenUsage(
                        prompt_tokens=u.get("prompt_tokens", 0),
                        completion_tokens=u.get("completion_tokens", 0),
                        total_tokens=u.get("total_tokens", 0),
                    )

                choices = event.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                text = delta.get("content", "")
                if not text and hasattr(delta, "reasoning_content"):
                    text = getattr(delta, "reasoning_content", "") or ""
                if text:
                    full_content += text
                    yield LLMResponse(
                        content=text,
                        provider=self.provider_name,
                        model=payload["model"],
                        usage=TokenUsage(),
                        latency_ms=0.0,
                    )

            # 兜底：如果没有收到 usage，按已生成内容估算
            if usage is None:
                usage = TokenUsage()

            # 最终 yield 一个携带完整 usage 的空内容标记（可选）
            yield LLMResponse(
                content="",
                provider=self.provider_name,
                model=payload["model"],
                usage=usage,
                latency_ms=0.0,
                meta={"finish_reason": "stop"},
            )


# 别名
KimiAdapter = OpenAIAdapter
DeepSeekAdapter = OpenAIAdapter

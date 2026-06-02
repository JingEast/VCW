"""Google Gemini Adapter。

API 文档: https://ai.google.dev/api/rest
使用 Gemini REST API（非 Vertex AI）。
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
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from .retry import with_llm_retry


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini Adapter。

    Args:
        api_key: Gemini API key。
        base_url: 默认 https://generativelanguage.googleapis.com/v1beta。
        model: 默认 gemini-1.5-pro-latest。
    """

    def __init__(
        self,
        provider_name: str = "gemini",
        *,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "gemini-1.5-pro-latest",
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            **kwargs,
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------

    @with_llm_retry(max_retries=3, backoff_initial=1.0)
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        # Gemini 使用 contents 格式
        contents = []
        system_instruction = None
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
                continue
            # Gemini role: user / model
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": m["content"]}],
            })

        payload: dict[str, Any] = {
            "contents": contents,
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction

        generation_config: dict[str, Any] = {}
        if "temperature" in kwargs:
            generation_config["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            generation_config["max_output_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            generation_config["top_p"] = kwargs["top_p"]
        if generation_config:
            payload["generation_config"] = generation_config

        model = kwargs.get("model") or self.model
        url = f"/models/{model}:generateContent?key={self.api_key}"

        t0 = time.perf_counter()
        trace_id = kwargs.pop("trace_id", None)
        extra_headers = {"X-Trace-Id": trace_id} if trace_id else None
        try:
            resp = self._client.post(url, json=payload, headers=extra_headers)
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

        candidates = data.get("candidates", [{}])
        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])
        content = ""
        for part in content_parts:
            content += part.get("text", "")

        usage_meta = data.get("usageMetadata", {})
        token_usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=model,
            usage=token_usage,
            latency_ms=latency_ms,
            meta={"finish_reason": candidate.get("finishReason")},
            raw_response=data,
        )

    # ------------------------------------------------------------------
    # embed
    # ------------------------------------------------------------------

    @with_llm_retry(max_retries=3, backoff_initial=1.0)
    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        model = kwargs.get("model") or getattr(self.config, "embed_model", "text-embedding-004")

        # Gemini embed 单次最多 100 个文本
        requests = [{"model": f"models/{model}", "content": {"parts": [{"text": t}]}} for t in texts]
        payload = {"requests": requests}

        url = f"/models/{model}:batchEmbedContents?key={self.api_key}"

        trace_id = kwargs.pop("trace_id", None)
        extra_headers = {"X-Trace-Id": trace_id} if trace_id else None
        try:
            resp = self._client.post(url, json=payload, headers=extra_headers)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"{self.provider_name} embed 超时", provider=self.provider_name
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._raise_from_http_error(exc)

        data = resp.json()
        embeddings = [e["values"] for e in data.get("embeddings", [])]
        return embeddings

    # ------------------------------------------------------------------
    # health check
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        try:
            model = self.model
            url = f"/models/{model}?key={self.api_key}"
            trace_id = getattr(self, "_last_trace_id", None)
            extra_headers = {"X-Trace-Id": trace_id} if trace_id else None
            resp = self._client.get(url, timeout=5.0, headers=extra_headers)
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
        status = exc.response.status_code
        try:
            body = exc.response.json()
            msg = body.get("error", {}).get("message", str(exc))
            code = body.get("error", {}).get("code", "")
        except Exception:
            msg = str(exc)
            code = ""

        if status == 401 or status == 403:
            raise LLMAuthenticationError(msg, provider=self.provider_name, code=code) from exc
        if status == 429:
            raise LLMRateLimitError(msg, provider=self.provider_name, code=code) from exc
        if status == 400:
            raise LLMBadRequestError(msg, provider=self.provider_name, code=code) from exc
        if status >= 500:
            raise LLMServiceUnavailableError(msg, provider=self.provider_name, code=code) from exc
        raise LLMAdapterError(msg, provider=self.provider_name, code=code) from exc

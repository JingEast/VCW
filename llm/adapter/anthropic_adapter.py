"""Anthropic Claude Adapter。

API 文档: https://docs.anthropic.com/claude/reference/messages_post
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
    LLMNotImplementedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from .retry import with_llm_retry


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude Adapter。

    Args:
        api_key: Anthropic API key (x-api-key)。
        base_url: 默认 https://api.anthropic.com/v1。
        model: 默认 claude-3-opus-20240229。
    """

    def __init__(
        self,
        provider_name: str = "anthropic",
        *,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "claude-3-opus-20240229",
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            provider_name=provider_name,
            api_key=api_key,
            base_url=base_url or "https://api.anthropic.com/v1",
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            **kwargs,
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
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
        # Anthropic 使用 system 参数而非 system message
        system = kwargs.get("system")
        anthropic_messages = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content")
                continue
            anthropic_messages.append({"role": m["role"], "content": m["content"]})

        payload: dict[str, Any] = {
            "model": kwargs.get("model") or self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
        if system:
            payload["system"] = system
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop_sequences"] = kwargs["stop"] if isinstance(kwargs["stop"], list) else [kwargs["stop"]]

        t0 = time.perf_counter()
        trace_id = kwargs.pop("trace_id", None)
        extra_headers = {"X-Trace-Id": trace_id} if trace_id else None
        try:
            resp = self._client.post("/messages", json=payload, headers=extra_headers)
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

        content_blocks = data.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )

        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=payload["model"],
            usage=token_usage,
            latency_ms=latency_ms,
            meta={"stop_reason": data.get("stop_reason")},
            raw_response=data,
        )

    # ------------------------------------------------------------------
    # embed —— Anthropic 暂不支持
    # ------------------------------------------------------------------

    @with_llm_retry(max_retries=3, backoff_initial=1.0)
    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise LLMNotImplementedError(
            "Anthropic 暂不支持 embedding API",
            provider=self.provider_name,
        )

    # ------------------------------------------------------------------
    # health check
    # ------------------------------------------------------------------

    def health_check(self) -> HealthStatus:
        try:
            # Anthropic 没有公开的 models list，用轻量 messages 探测
            trace_id = getattr(self, "_last_trace_id", None)
            extra_headers = {"X-Trace-Id": trace_id} if trace_id else None
            resp = self._client.post(
                "/messages",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
                timeout=5.0,
                headers=extra_headers,
            )
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
            error_type = body.get("error", {}).get("type", "")
        except Exception:
            msg = str(exc)
            error_type = ""

        if status == 401:
            raise LLMAuthenticationError(msg, provider=self.provider_name, code=error_type) from exc
        if status == 429:
            raise LLMRateLimitError(msg, provider=self.provider_name, code=error_type) from exc
        if status == 400:
            raise LLMBadRequestError(msg, provider=self.provider_name, code=error_type) from exc
        if status == 403:
            raise LLMContentFilterError(msg, provider=self.provider_name, code=error_type) from exc
        if status >= 500:
            raise LLMServiceUnavailableError(msg, provider=self.provider_name, code=error_type) from exc
        raise LLMAdapterError(msg, provider=self.provider_name, code=error_type) from exc

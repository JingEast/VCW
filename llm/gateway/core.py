"""LLM Gateway —— 统一调用入口。

所有 LLM 调用（生成、流式生成、嵌入、健康检查）均通过此类完成。
Gateway 本身不实现任何 provider 细节，仅负责编排：
  cache → tracing(pre) → adapter.chat → tracing(post) → metrics
  失败时按 fallback strategy 切换下一个 provider。
"""

from __future__ import annotations

import time
from typing import Any, Iterator, Optional, Self

from llm.adapter.base import BaseLLMAdapter, LLMResponse
from llm.cache.base import BaseCacheBackend
from llm.fallback.base import BaseFallbackStrategy
from llm.metrics.base import BaseMetricsCollector, MetricLabels
from llm.tracing.base import BaseTracingMiddleware
from llm.tracing.otel_tracing import GatewayTracer

from .config import GatewayConfig
from .registry import ProviderRegistry


class LLMGateway:
    """LLM 统一调用入口。

    Usage:
        gateway = LLMGateway(config, registry)
        gateway.attach_tracing(...).attach_metrics(...)
        response = gateway.chat([{"role": "user", "content": "hi"}], provider="kimi")
    """

    def __init__(
        self,
        config: GatewayConfig,
        registry: ProviderRegistry,
    ) -> None:
        self.config = config
        self.registry = registry
        self._tracing: Optional[BaseTracingMiddleware] = None
        self._metrics: Optional[BaseMetricsCollector] = None
        self._cache: Optional[BaseCacheBackend] = None
        self._fallback: Optional[BaseFallbackStrategy] = None

    # ------------------------------------------------------------------
    # 中间件挂载（builder 模式）
    # ------------------------------------------------------------------

    def attach_tracing(self, tracing: BaseTracingMiddleware) -> Self:
        """挂载链路追踪中间件。"""
        self._tracing = tracing
        return self

    def attach_metrics(self, metrics: BaseMetricsCollector) -> Self:
        """挂载指标采集中间件。"""
        self._metrics = metrics
        return self

    def attach_cache(self, cache: BaseCacheBackend) -> Self:
        """挂载缓存后端。"""
        self._cache = cache
        return self

    def attach_fallback(self, fallback: BaseFallbackStrategy) -> Self:
        """挂载 fallback 策略。"""
        self._fallback = fallback
        return self

    # ------------------------------------------------------------------
    # 核心调用方法
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: Optional[str] = None,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """多轮对话生成。

        执行流程：
          1. 确定 provider
          2. 查询 cache（命中则直接返回）
          3. tracing.pre_call
          4. adapter.chat（含 retry）
          5. tracing.post_call
          6. metrics.record
          7. 写入 cache
          8. 返回 LLMResponse
        """
        provider_name = self._resolve_provider(provider)
        adapter = self.registry.get(provider_name)

        # 2. cache
        if self._cache is not None:
            cache_key = self._cache.make_key(messages, provider_name, **kwargs)
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._record_metrics(
                    provider=provider_name,
                    model=cached.response.model,
                    status="cached",
                    user=user,
                    latency_ms=0.0,
                    usage=cached.response.usage,
                    request_id=request_id,
                )
                return cached.response

        # 3. tracing pre
        trace_ctx = None
        if self._tracing is not None:
            trace_ctx = self._tracing.pre_call(messages, provider_name, **kwargs)

        # 4. adapter.chat（含 model call span）
        t0 = time.perf_counter()
        error: Optional[Exception] = None
        response: Optional[LLMResponse] = None
        try:
            with GatewayTracer.model_call_span(provider_name, adapter.model):
                response = adapter.chat(messages, **kwargs)
        except Exception as exc:
            error = exc
            raise
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000

            # 5. tracing post
            if self._tracing is not None and trace_ctx is not None:
                self._tracing.post_call(trace_ctx, response=response, error=error)

            # 6. metrics
            status = "success" if error is None else "failure"
            model = response.model if response is not None else adapter.model
            usage = response.usage if response is not None else None
            self._record_metrics(
                provider=provider_name,
                model=model,
                status=status,
                user=user,
                latency_ms=latency_ms,
                usage=usage,
                request_id=request_id,
            )

            # 7. cache write
            if self._cache is not None and error is None and response is not None:
                from llm.cache.base import CacheEntry
                self._cache.set(cache_key, CacheEntry(response=response, ttl_seconds=self.config.cache_ttl_seconds))

        if response is None:
            raise RuntimeError("adapter.chat 返回了 None，Gateway 内部状态异常")
        return response

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        provider: Optional[str] = None,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """单轮补全（包装为 chat）。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(
            messages,
            provider=provider,
            user=user,
            request_id=request_id,
            **kwargs,
        )

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        provider: Optional[str] = None,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Iterator[LLMResponse]:
        """流式生成。

        执行流程与 chat 类似，但 tracing/metrics 在迭代结束后统一结算。
        """
        provider_name = self._resolve_provider(provider)
        adapter = self.registry.get(provider_name)

        trace_ctx = None
        if self._tracing is not None:
            trace_ctx = self._tracing.pre_call(messages, provider_name, **kwargs)

        t0 = time.perf_counter()
        error: Optional[Exception] = None
        last_response: Optional[LLMResponse] = None
        try:
            for chunk in adapter.generate_stream(messages, **kwargs):
                last_response = chunk
                yield chunk
        except Exception as exc:
            error = exc
            raise
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            if self._tracing is not None and trace_ctx is not None:
                self._tracing.post_call(trace_ctx, response=last_response, error=error)

            status = "success" if error is None else "failure"
            model = last_response.model if last_response is not None else adapter.model
            usage = last_response.usage if last_response is not None else None
            self._record_metrics(
                provider=provider_name,
                model=model,
                status=status,
                user=user,
                latency_ms=latency_ms,
                usage=usage,
                request_id=request_id,
            )

    def embed(
        self,
        texts: list[str],
        *,
        provider: Optional[str] = None,
        user: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        """文本向量化。

        直接委托给对应 adapter，不走 cache/fallback（embedding 通常不重）。
        """
        provider_name = self._resolve_provider(provider)
        adapter = self.registry.get(provider_name)

        t0 = time.perf_counter()
        error: Optional[Exception] = None
        result: Optional[list[list[float]]] = None
        try:
            result = adapter.embed(texts, **kwargs)
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            self._record_metrics(
                provider=provider_name,
                model=adapter.model,
                status="success" if error is None else "failure",
                user=user,
                latency_ms=latency_ms,
                usage=None,
                request_id=request_id,
            )

    def health_check(self, provider: Optional[str] = None) -> dict[str, Any]:
        """健康检查。

        Args:
            provider: 指定 provider；None 则检查全部。

        Returns:
            {provider_name: {"status": ..., "latency_ms": ...}}
        """
        if provider is not None:
            adapter = self.registry.get(provider)
            return {provider: {"status": adapter.health_check().value}}
        return {
            name: {"status": status.value}
            for name, status in self.registry.health_check_all().items()
        }

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _resolve_provider(self, provider: Optional[str]) -> str:
        """解析最终使用的 provider 名称。"""
        if provider is not None:
            return provider
        if self.config.default_provider is not None:
            return self.config.default_provider
        providers = self.registry.list()
        if not providers:
            raise RuntimeError("ProviderRegistry 为空，请先注册 provider")
        return providers[0]

    def _record_metrics(
        self,
        *,
        provider: str,
        model: str,
        status: str,
        user: Optional[str],
        latency_ms: float,
        usage: Any,
        request_id: Optional[str],
    ) -> None:
        """统一 metrics 记录入口。"""
        if self._metrics is None:
            return
        labels = MetricLabels(
            provider=provider,
            model=model,
            status=status,
            user=user,
        )
        prompt_tokens = usage.prompt_tokens if usage is not None else 0
        completion_tokens = usage.completion_tokens if usage is not None else 0
        self._metrics.observe_request_duration(labels, latency_ms)
        self._metrics.increment_request_total(labels)
        self._metrics.record(
            labels=labels,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=0.0,  # collector 内部根据 model+tokens 自动计算
            request_id=request_id,
        )

    def __repr__(self) -> str:
        return (
            f"<LLMGateway providers={self.registry.list()} "
            f"tracing={self._tracing is not None} "
            f"metrics={self._metrics is not None} "
            f"cache={self._cache is not None} "
            f"fallback={self._fallback is not None}>"
        )

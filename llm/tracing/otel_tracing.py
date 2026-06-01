"""OpenTelemetry Tracing Middleware。

将 Gateway 的 pre_call / post_call 映射为 OpenTelemetry Span，
支持嵌套子 span（model call、retry、fallback）。

若 opentelemetry 未安装，自动降级为 NoopTracer，保证代码可运行。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from llm.adapter.base import LLMResponse

from .base import BaseTracingMiddleware, TraceContext
from .exporter_config import TracingExporterConfig


# ------------------------------------------------------------------------------
# Optional OpenTelemetry imports with graceful fallback
# ------------------------------------------------------------------------------

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment,misc]
    StatusCode = None  # type: ignore[assignment,misc]
    TraceContextTextMapPropagator = None  # type: ignore[assignment,misc]


# ------------------------------------------------------------------------------
# No-op fallback types for environments without opentelemetry
# ------------------------------------------------------------------------------

class _NoopSpan:
    """兼容 opentelemetry Span 接口的 no-op 实现。"""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attrs: Dict[str, Any]) -> None:
        pass

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
    ) -> None:
        pass

    def set_status(self, status: Any, description: Optional[str] = None) -> None:
        pass

    def record_exception(self, exception: Exception, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def end(self, end_time: Optional[int] = None) -> None:
        pass

    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoopTracer:
    """兼容 opentelemetry Tracer 接口的 no-op 实现。"""

    def start_span(
        self,
        name: str,
        context: Optional[Any] = None,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> _NoopSpan:
        return _NoopSpan()

    def start_as_current_span(
        self,
        name: str,
        context: Optional[Any] = None,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> _NoopSpan:
        return _NoopSpan()


def _get_tracer(name: str = "llm.gateway") -> Any:
    """获取 tracer，若 opentelemetry 未安装则返回 NoopTracer。"""
    if _OTEL_AVAILABLE and trace is not None:
        return trace.get_tracer(name)
    return _NoopTracer()


# ------------------------------------------------------------------------------
# OtelTracingMiddleware
# ------------------------------------------------------------------------------


class OtelTracingMiddleware(BaseTracingMiddleware):
    """OpenTelemetry Tracing Middleware。

    每个 Gateway 调用（chat/complete/embed）映射为一个 Span：
      - span name: llm.request
      - attributes: provider, model, user, messages_count, temperature, max_tokens
      - events: cache.hit / cache.miss, model.call.start, model.call.end
      - status: OK / ERROR

    子 span 可通过 GatewayTracer 上下文管理器在 Gateway 内部创建。
    """

    def __init__(
        self,
        tracer: Optional[Any] = None,
        config: Optional[TracingExporterConfig] = None,
    ) -> None:
        self.tracer = tracer or _get_tracer()
        self.config = config
        self._spans: dict[str, Any] = {}

    def pre_call(
        self,
        messages: list[dict[str, str]],
        provider: str,
        **kwargs: Any,
    ) -> TraceContext:
        """创建 Gateway 级 span。"""
        trace_id = kwargs.get("trace_id")
        span_name = kwargs.get("span_name", "llm.request")
        user = kwargs.get("user")
        model = kwargs.get("model", "")

        parent_context = None
        if trace_id and _OTEL_AVAILABLE and TraceContextTextMapPropagator is not None:
            # 尝试从外部 propagator 恢复 parent context
            carrier = {"traceparent": trace_id}
            parent_context = TraceContextTextMapPropagator().extract(carrier=carrier)

        span = self.tracer.start_span(
            span_name,
            context=parent_context,
            attributes={
                "llm.provider": provider,
                "llm.model": model or "",
                "llm.user": user or "",
                "llm.messages.count": len(messages),
            },
        )

        # 记录可选参数
        if "temperature" in kwargs:
            span.set_attribute("llm.temperature", kwargs["temperature"])
        if "max_tokens" in kwargs:
            span.set_attribute("llm.max_tokens", kwargs["max_tokens"])

        span_ctx = getattr(span, "get_span_context", lambda: None)()
        span_id = getattr(span_ctx, "span_id", "") if span_ctx is not None else ""
        ctx = TraceContext(
            trace_id=trace_id or str(span_id),
            span_id=str(span_id),
            attributes={"span": span, "start_ns": time.time_ns()},
        )
        self._spans[ctx.trace_id] = span
        return ctx

    def post_call(
        self,
        ctx: TraceContext,
        response: Optional[LLMResponse] = None,
        error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """结束 Gateway 级 span。"""
        span = ctx.attributes.get("span")
        if span is None:
            span = self._spans.pop(ctx.trace_id, None)
        if span is None:
            return

        start_ns = ctx.attributes.get("start_ns")
        if start_ns:
            latency_ms = (time.time_ns() - start_ns) / 1_000_000
            span.set_attribute("llm.latency_ms", round(latency_ms, 3))

        if response is not None:
            span.set_attribute("llm.response.model", response.model)
            span.set_attribute("llm.response.tokens.prompt", response.usage.prompt_tokens)
            span.set_attribute("llm.response.tokens.completion", response.usage.completion_tokens)
            span.set_attribute("llm.response.tokens.total", response.usage.total_tokens)

        if error is not None:
            if StatusCode is not None:
                span.set_status(StatusCode.ERROR, str(error))
            span.record_exception(error)
        else:
            if StatusCode is not None:
                span.set_status(StatusCode.OK)

        span.end()
        self._spans.pop(ctx.trace_id, None)

    def start_child_span(self, name: str, parent_ctx: TraceContext, attributes: Optional[Dict[str, Any]] = None) -> Any:
        """从 parent Gateway span 启动子 span。

        供 Gateway 内部在 model call / retry / fallback 阶段使用。
        """
        parent_span = parent_ctx.attributes.get("span")
        ctx = None
        if _OTEL_AVAILABLE and parent_span is not None:
            from opentelemetry.trace import set_span_in_context
            ctx = set_span_in_context(parent_span)
        return self.tracer.start_span(name, context=ctx, attributes=attributes or {})


# ------------------------------------------------------------------------------
# GatewayTracer helper —— 供 Gateway 内部直接创建子 span
# ------------------------------------------------------------------------------

class GatewayTracer:
    """Gateway 内部使用的 Tracer 助手。

    通过上下文管理器在关键代码段创建子 span：
      - llm.model.call
      - llm.retry
      - llm.fallback
    """

    def __init__(self, tracer: Optional[Any] = None) -> None:
        self.tracer = tracer or _get_tracer()

    @staticmethod
    def model_call_span(
        provider: str,
        model: str,
        tracer: Optional[Any] = None,
    ) -> Any:
        """模型调用子 span 上下文管理器。"""
        t = tracer or _get_tracer()
        return t.start_as_current_span(
            "llm.model.call",
            attributes={
                "llm.provider": provider,
                "llm.model": model,
            },
        )

    @staticmethod
    def retry_span(
        attempt: int,
        max_attempts: int,
        exception: Optional[Exception] = None,
        tracer: Optional[Any] = None,
    ) -> Any:
        """重试事件 span。"""
        t = tracer or _get_tracer()
        span = t.start_span(
            "llm.retry",
            attributes={
                "retry.attempt": attempt,
                "retry.max_attempts": max_attempts,
            },
        )
        if exception is not None:
            span.set_attribute("retry.exception", type(exception).__name__)
            span.record_exception(exception)
        span.end()
        return span

    @staticmethod
    def fallback_span(
        from_provider: str,
        to_provider: str,
        reason: str,
        tracer: Optional[Any] = None,
    ) -> Any:
        """Fallback 决策子 span。"""
        t = tracer or _get_tracer()
        span = t.start_span(
            "llm.fallback",
            attributes={
                "fallback.from_provider": from_provider,
                "fallback.to_provider": to_provider,
                "fallback.reason": reason,
            },
        )
        span.end()
        return span

"""基于日志的 Tracing 实现。"""

import logging
import time
import uuid
from typing import Any, Optional

from .base import BaseTracingMiddleware, TraceContext
from llm.adapter.base import LLMResponse


class LogTracingMiddleware(BaseTracingMiddleware):
    """将追踪信息写入 Python logging。

    输出格式为结构化 JSON（可通过 logging formatter 进一步处理）。
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("llm.gateway.trace")

    def pre_call(
        self,
        messages: list[dict[str, str]],
        provider: str,
        **kwargs: Any,
    ) -> TraceContext:
        ctx = TraceContext(
            trace_id=kwargs.get("trace_id") or uuid.uuid4().hex[:16],
            span_id=uuid.uuid4().hex[:8],
            start_time_ns=time.time_ns(),
            attributes={"provider": provider},
        )
        self.logger.info(
            "[LLM-TRACE-START] trace_id=%s provider=%s",
            ctx.trace_id,
            provider,
        )
        return ctx

    def post_call(
        self,
        ctx: TraceContext,
        response: Optional[LLMResponse] = None,
        error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        latency_ms = 0.0
        if ctx.start_time_ns:
            latency_ms = (time.time_ns() - ctx.start_time_ns) / 1_000_000

        if error:
            self.logger.warning(
                "[LLM-TRACE-ERROR] trace_id=%s latency_ms=%.2f error=%s",
                ctx.trace_id,
                latency_ms,
                error,
            )
        else:
            self.logger.info(
                "[LLM-TRACE-END] trace_id=%s latency_ms=%.2f "
                "provider=%s model=%s",
                ctx.trace_id,
                latency_ms,
                response.provider if response else "",
                response.model if response else "",
            )

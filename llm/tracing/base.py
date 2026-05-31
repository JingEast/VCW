"""Tracing 中间件抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from llm.adapter.base import LLMResponse


@dataclass(frozen=True)
class TraceContext:
    """追踪上下文。"""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time_ns: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


class BaseTracingMiddleware(ABC):
    """Tracing 中间件抽象基类。

    Gateway 在每次调用时执行：
      1. ctx = pre_call(prompt, provider)
      2. response = adapter.generate(prompt)
      3. post_call(ctx, response, error)
    """

    @abstractmethod
    def pre_call(
        self,
        messages: list[dict[str, str]],
        provider: str,
        **kwargs: Any,
    ) -> TraceContext:
        """在 LLM 调用前执行，创建追踪上下文。"""
        ...

    @abstractmethod
    def post_call(
        self,
        ctx: TraceContext,
        response: Optional[LLMResponse] = None,
        error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """在 LLM 调用后执行，记录结果或异常。"""
        ...

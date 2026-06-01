"""Tracing 装饰器 —— 为 retry 和 fallback 自动附加 span/event。

用法：
    @trace_retry()
    def my_retryable_func(...):
        ...

    @trace_fallback()
    def my_fallback_strategy(...):
        ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional, TypeVar

from llm.tracing.otel_tracing import _get_tracer

F = TypeVar("F", bound=Callable[..., Any])


def trace_retry(
    span_name: str = "llm.retry",
    tracer: Optional[Any] = None,
) -> Callable[[F], F]:
    """装饰器：为可重试函数附加 retry span。

    记录每次重试的 attempt、exception type、backoff。
    注意：此装饰器应置于 tenacity retry 装饰器**之内**（靠近函数），
    或配合 tenacity 的 before_sleep 回调使用。
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t = tracer or _get_tracer()
            # 尝试从 kwargs 中提取 attempt 信息
            attempt = kwargs.pop("_trace_attempt", 1)
            max_attempts = kwargs.pop("_trace_max_attempts", 3)
            with t.start_as_current_span(
                span_name,
                attributes={
                    "retry.attempt": attempt,
                    "retry.max_attempts": max_attempts,
                    "retry.function": fn.__qualname__,
                },
            ) as span:
                try:
                    result = fn(*args, **kwargs)
                    span.set_attribute("retry.result", "success")
                    return result
                except Exception as exc:
                    span.set_attribute("retry.exception", type(exc).__name__)
                    span.record_exception(exc)
                    raise
        return wrapper  # type: ignore[return-value]
    return decorator


def trace_fallback(
    span_name: str = "llm.fallback",
    tracer: Optional[Any] = None,
) -> Callable[[F], F]:
    """装饰器：为 fallback decide 方法附加 fallback span。

    记录 from_provider、to_provider、reason。
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t = tracer or _get_tracer()
            # 尝试从参数中提取 provider 信息
            failed_provider = kwargs.get("failed_provider") or (args[0] if len(args) > 0 else "")
            with t.start_as_current_span(
                span_name,
                attributes={
                    "fallback.function": fn.__qualname__,
                    "fallback.failed_provider": str(failed_provider),
                },
            ) as span:
                result = fn(*args, **kwargs)
                if result is not None:
                    span.set_attribute("fallback.to_provider", getattr(result, "provider", ""))
                    span.set_attribute("fallback.reason", getattr(result, "reason", ""))
                else:
                    span.set_attribute("fallback.result", "exhausted")
                return result
        return wrapper  # type: ignore[return-value]
    return decorator

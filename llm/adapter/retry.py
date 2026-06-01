"""Retry Policy —— 基于 tenacity 的统一重试策略。

装饰器 `with_llm_retry` 供各 adapter 的 chat / embed 方法使用，
自动处理 timeout、rate limit、5xx 等可重试异常。

新增：支持 retry span 注入，每次重试前记录 OpenTelemetry event。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .exceptions import (
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)

logger = logging.getLogger("llm.adapter.retry")

T = TypeVar("T")

# 默认可重试异常类型
RETRYABLE_EXCEPTIONS = (
    LLMTimeoutError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
)


def _before_sleep_with_trace(retry_state: Any) -> None:
    """tenacity before_sleep 回调：记录日志 + 可选 retry span event。"""
    attempt_number = retry_state.attempt_number
    max_attempts = getattr(retry_state, "max_attempt_number", 3)
    exception = retry_state.outcome.exception() if retry_state.outcome else None

    # 记录 retry span event（若当前存在 otel span）
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and getattr(span, "is_recording", lambda: False)():
            span.add_event(
                "llm.retry",
                {
                    "retry.attempt": attempt_number,
                    "retry.max_attempts": max_attempts,
                    "retry.exception": type(exception).__name__ if exception else "",
                    "retry.wait_seconds": getattr(retry_state.next_action, "sleep", 0.0) if retry_state.next_action else 0.0,
                },
            )
    except ImportError:
        pass

    # 原有日志
    logger.warning(
        "[LLM-RETRY] attempt=%d/%d exception=%s wait=%.2fs",
        attempt_number,
        max_attempts,
        type(exception).__name__ if exception else "",
        getattr(retry_state.next_action, "sleep", 0.0) if retry_state.next_action else 0.0,
    )


def with_llm_retry(
    max_retries: int = 3,
    backoff_initial: float = 1.0,
    backoff_max: float = 60.0,
    retryable_exceptions: tuple = RETRYABLE_EXCEPTIONS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """为 adapter 方法附加重试策略的装饰器工厂。

    Args:
        max_retries: 最大重试次数（含首次调用）。
        backoff_initial: 指数退避初始值（秒）。
        backoff_max: 退避上限（秒）。
        retryable_exceptions: 触发重试的异常类型元组。

    Returns:
        tenacity retry 装饰器。
    """
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential_jitter(
            initial=backoff_initial,
            max=backoff_max,
            exp_base=2,
        ),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=_before_sleep_with_trace,
        reraise=True,
    )

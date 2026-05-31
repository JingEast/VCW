"""Prompt Retry 策略 —— 指数退避与可重试错误分类。

职责：
  1. 对特定错误（超时、速率限制、服务端错误）执行重试。
  2. 对不可逆错误（认证失败、参数错误）立即失败。
  3. 支持固定间隔、线性退避、指数退避三种策略。
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Type, Union


@dataclass
class RetryConfig:
    """重试配置。"""

    max_retries: int = 3
    base_delay_ms: float = 500.0
    max_delay_ms: float = 30000.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        RuntimeError,
    )
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
    )


class IPromptRetryPolicy(ABC):
    """重试策略接口。"""

    @abstractmethod
    def execute(self, fn: Callable, *args, **kwargs):
        """执行带重试的函数调用。"""


class PromptRetryPolicy(IPromptRetryPolicy):
    """默认重试策略（指数退避 + 错误分类）。"""

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self._config = config or RetryConfig()

    def execute(self, fn: Callable, *args, **kwargs):
        last_exception: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt == self._config.max_retries:
                    break
                if not self._is_retryable(exc):
                    break
                delay = self._compute_delay(attempt)
                time.sleep(delay / 1000.0)

        if last_exception is not None:
            raise last_exception
        # unreachable, but make type checker happy
        return None

    def _is_retryable(self, exc: Exception) -> bool:
        for exc_type in self._config.non_retryable_exceptions:
            if isinstance(exc, exc_type):
                return False
        for exc_type in self._config.retryable_exceptions:
            if isinstance(exc, exc_type):
                return True
        # default: unknown exceptions are non-retryable
        return False

    def _compute_delay(self, attempt: int) -> float:
        """计算退避延迟（毫秒）。"""
        delay = self._config.base_delay_ms * (self._config.backoff_multiplier ** attempt)
        delay = min(delay, self._config.max_delay_ms)
        if self._config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay


class PromptRetryWithFallback(PromptRetryPolicy):
    """重试 + Fallback 组合策略。

    对单个模型先重试，全部失败后切换到下一个模型。
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        fallback_strategy=None,
    ) -> None:
        super().__init__(retry_config)
        self._fallback = fallback_strategy

    def execute_with_fallback(
        self,
        primary_fn: Callable,
        fallback_fns: List[Callable],
        *args,
        **kwargs,
    ):
        from .prompt_fallback import DegradeContent

        def wrapped_primary():
            return self.execute(primary_fn, *args, **kwargs)

        wrapped_fallbacks = [
            lambda fn=fn: self.execute(fn, *args, **kwargs)
            for fn in fallback_fns
        ]

        if self._fallback is not None:
            return self._fallback.execute(
                wrapped_primary,
                wrapped_fallbacks,
                degrade_content=DegradeContent(content="", success=False),
            )

        # 无 fallback，仅重试 primary
        return self.execute(primary_fn, *args, **kwargs)

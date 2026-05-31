"""Fallback 策略抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class FallbackResult:
    """Fallback 决策结果。"""

    provider: str
    reason: str
    attempts: int


class BaseFallbackStrategy(ABC):
    """Fallback 策略抽象基类。

    Gateway 在主 provider 失败后调用 decide()，
    获取下一个应尝试的 provider。
    """

    @abstractmethod
    def decide(
        self,
        failed_provider: str,
        available_providers: List[str],
        error: Optional[Exception] = None,
    ) -> Optional[FallbackResult]:
        """决定下一个 fallback provider。

        Args:
            failed_provider: 刚刚失败的 provider 名称。
            available_providers: 当前所有可用 provider 列表。
            error: 失败异常（可选，供策略做异常类型判断）。

        Returns:
            FallbackResult 或 None（无可用备用）。
        """
        ...

    @abstractmethod
    def record_result(
        self,
        provider: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """记录 provider 调用结果，供策略动态调整。"""
        ...

"""Metrics 采集抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MetricLabels:
    """指标标签。"""

    provider: str
    model: str
    status: str  # "success" | "failure" | "cached"
    user: Optional[str] = None


class BaseMetricsCollector(ABC):
    """Metrics 采集抽象基类。

    Gateway 在每次调用结束后执行 record()，
    具体实现决定如何存储/暴露指标。
    """

    @abstractmethod
    def record(
        self,
        labels: MetricLabels,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        request_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """记录一次 LLM 调用指标。

        Args:
            labels: provider + model + status + user 标签。
            latency_ms: 端到端延迟（毫秒）。
            prompt_tokens: prompt token 数。
            completion_tokens: completion token 数。
            cost: 本次调用成本（USD）。
            request_id: 可选请求追踪 ID。
        """
        ...

    @abstractmethod
    def observe_request_duration(
        self,
        labels: MetricLabels,
        duration_ms: float,
    ) -> None:
        """记录请求耗时 histogram。"""
        ...

    @abstractmethod
    def increment_request_total(
        self,
        labels: MetricLabels,
    ) -> None:
        """记录请求总数 counter。"""
        ...

"""Prompt 指标收集器 —— 聚合 LLM 调用性能与成本数据。

职责：
  1. 记录每次调用的 token 消耗、延迟、成功率、成本。
  2. 提供聚合指标（总量、平均值、百分位、成本）。
  3. 支持按 model / 时间窗口 / 状态分组聚合。
  4. 支持 Prometheus 指标暴露。
"""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Optional Prometheus integration
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

# ------------------------------------------------------------------------------
# Model Pricing (USD per 1K tokens)
# ------------------------------------------------------------------------------

MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # (input_price_per_1k, output_price_per_1k)
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "moonshot-v1-8k": (0.012, 0.012),
    "moonshot-v1-32k": (0.024, 0.024),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "default": (0.01, 0.01),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """根据 model 和 token 数计算成本（USD）。"""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_price, output_price = pricing
    cost = (input_tokens / 1000.0) * input_price + (output_tokens / 1000.0) * output_price
    return round(cost, 6)


# ------------------------------------------------------------------------------
# Data Classes
# ------------------------------------------------------------------------------

@dataclass
class PromptCallInfo:
    """单次调用的原始指标数据。"""

    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = True
    model: str = ""
    timestamp: Optional[float] = None


@dataclass
class PromptMetricsSnapshot:
    """聚合后的指标快照。"""

    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    model_distribution: Dict[str, int] = field(default_factory=dict)
    model_costs: Dict[str, float] = field(default_factory=dict)
    time_window_seconds: Optional[int] = None


# ------------------------------------------------------------------------------
# Interface
# ------------------------------------------------------------------------------

class IPromptMetricsCollector(ABC):
    """指标收集器接口。"""

    @abstractmethod
    def record(self, info: PromptCallInfo) -> None:
        """记录一次调用的指标。"""

    @abstractmethod
    def get_snapshot(self, window_seconds: Optional[int] = None) -> PromptMetricsSnapshot:
        """获取全局聚合指标；可选按时间窗口过滤。"""

    @abstractmethod
    def get_by_model(self, model: str, window_seconds: Optional[int] = None) -> PromptMetricsSnapshot:
        """按 model 分组获取聚合指标。"""

    @abstractmethod
    def reset(self) -> None:
        """清空所有记录。"""

    @abstractmethod
    def expose_prometheus(self) -> bytes:
        """返回 Prometheus text format 指标。"""


# ------------------------------------------------------------------------------
# Implementation
# ------------------------------------------------------------------------------

class PromptMetricsCollector(IPromptMetricsCollector):
    """默认指标收集器（内存 + Prometheus）。"""

    def __init__(self, enable_prometheus: bool = True) -> None:
        self._records: List[PromptCallInfo] = []
        self._enable_prometheus = enable_prometheus and _PROMETHEUS_AVAILABLE

        self._prom_calls: Optional[Counter] = None
        self._prom_tokens: Optional[Counter] = None
        self._prom_cost: Optional[Counter] = None
        self._prom_latency: Optional[Histogram] = None
        self._prom_active: Optional[Gauge] = None

        if self._enable_prometheus:
            self._prom_calls = Counter(
                "prompt_calls_total",
                "Total number of prompt calls",
                ["model", "status"],
            )
            self._prom_tokens = Counter(
                "prompt_tokens_total",
                "Total number of tokens consumed",
                ["model", "type"],
            )
            self._prom_cost = Counter(
                "prompt_cost_total",
                "Total cost in USD",
                ["model"],
            )
            self._prom_latency = Histogram(
                "prompt_latency_seconds",
                "Prompt latency in seconds",
                ["model"],
                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            )
            self._prom_active = Gauge(
                "prompt_active_requests",
                "Number of currently active prompt requests",
            )

    def record(self, info: PromptCallInfo) -> None:
        self._records.append(info)
        cost = compute_cost(info.model, info.input_tokens, info.output_tokens)

        if self._enable_prometheus:
            assert self._prom_calls is not None
            assert self._prom_tokens is not None
            assert self._prom_cost is not None
            assert self._prom_latency is not None
            status = "success" if info.success else "error"
            self._prom_calls.labels(model=info.model or "unknown", status=status).inc()
            self._prom_tokens.labels(model=info.model or "unknown", type="input").inc(
                info.input_tokens
            )
            self._prom_tokens.labels(model=info.model or "unknown", type="output").inc(
                info.output_tokens
            )
            self._prom_cost.labels(model=info.model or "unknown").inc(cost)
            self._prom_latency.labels(model=info.model or "unknown").observe(
                info.latency_ms / 1000.0
            )

    def _filter_records(
        self, window_seconds: Optional[int] = None, model: Optional[str] = None
    ) -> List[PromptCallInfo]:
        import time as _time

        records = self._records
        if window_seconds is not None:
            cutoff = _time.time() - window_seconds
            records = [r for r in records if (r.timestamp or 0) >= cutoff]
        if model is not None:
            records = [r for r in records if r.model == model]
        return records

    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f
        if f == c:
            return sorted_values[f]
        return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)

    def get_snapshot(self, window_seconds: Optional[int] = None) -> PromptMetricsSnapshot:
        records = self._filter_records(window_seconds)
        return self._aggregate(records, window_seconds=window_seconds)

    def get_by_model(self, model: str, window_seconds: Optional[int] = None) -> PromptMetricsSnapshot:
        records = self._filter_records(window_seconds, model=model)
        return self._aggregate(records, window_seconds=window_seconds)

    def _aggregate(
        self, records: List[PromptCallInfo], window_seconds: Optional[int] = None
    ) -> PromptMetricsSnapshot:
        if not records:
            return PromptMetricsSnapshot(time_window_seconds=window_seconds)

        total_calls = len(records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_tokens = total_input + total_output
        total_cost = sum(
            compute_cost(r.model, r.input_tokens, r.output_tokens) for r in records
        )
        latencies = [r.latency_ms for r in records]
        latencies_sorted = sorted(latencies)
        success_count = sum(1 for r in records if r.success)

        model_dist: Dict[str, int] = {}
        model_costs: Dict[str, float] = {}
        for r in records:
            model_dist[r.model] = model_dist.get(r.model, 0) + 1
            cost = compute_cost(r.model, r.input_tokens, r.output_tokens)
            model_costs[r.model] = model_costs.get(r.model, 0.0) + cost

        return PromptMetricsSnapshot(
            total_calls=total_calls,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            total_cost=round(total_cost, 6),
            avg_latency_ms=round(statistics.mean(latencies), 3),
            p50_latency_ms=round(self._percentile(latencies_sorted, 50), 3),
            p90_latency_ms=round(self._percentile(latencies_sorted, 90), 3),
            p99_latency_ms=round(self._percentile(latencies_sorted, 99), 3),
            min_latency_ms=round(latencies_sorted[0], 3),
            max_latency_ms=round(latencies_sorted[-1], 3),
            success_rate=round(success_count / total_calls, 4),
            error_rate=round(1 - success_count / total_calls, 4),
            model_distribution=model_dist,
            model_costs={k: round(v, 6) for k, v in model_costs.items()},
            time_window_seconds=window_seconds,
        )

    def reset(self) -> None:
        self._records.clear()

    def expose_prometheus(self) -> bytes:
        if not self._enable_prometheus:
            return b"# Prometheus not enabled\n"
        return generate_latest()

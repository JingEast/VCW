"""基于日志的 Metrics 采集实现。"""

import logging
from typing import Optional

from .base import BaseMetricsCollector, MetricLabels


class LogMetricsCollector(BaseMetricsCollector):
    """将指标写入 Python logging。

    生产环境可替换为 TokenAccountingCollector。
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("llm.gateway.metrics")

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
        user_str = f" user={labels.user}" if labels.user else ""
        rid_str = f" request_id={request_id}" if request_id else ""
        self.logger.info(
            "[LLM-METRICS] provider=%s model=%s status=%s%s%s"
            " latency_ms=%.2f prompt_tokens=%d completion_tokens=%d total_tokens=%d cost_usd=%.6f",
            labels.provider,
            labels.model,
            labels.status,
            user_str,
            rid_str,
            latency_ms,
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            cost,
        )

    def observe_request_duration(
        self,
        labels: MetricLabels,
        duration_ms: float,
    ) -> None:
        self.logger.debug(
            "[LLM-METRICS-HISTOGRAM] provider=%s model=%s duration_ms=%.2f",
            labels.provider,
            labels.model,
            duration_ms,
        )

    def increment_request_total(
        self,
        labels: MetricLabels,
    ) -> None:
        self.logger.debug(
            "[LLM-METRICS-COUNTER] provider=%s model=%s status=%s +1",
            labels.provider,
            labels.model,
            labels.status,
        )

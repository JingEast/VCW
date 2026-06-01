"""Token Accounting —— 按请求/用户/模型维度的 Token 与成本统计。

职责：
  1. 记录每次 LLM 调用的 prompt_tokens / completion_tokens / total_tokens / cost。
  2. 支持 per-request 明细查询。
  3. 支持 per-user 聚合查询。
  4. 支持 per-model 聚合查询。
  5. 输出 Prometheus OpenMetrics 格式。
  6. 输出 JSON API 格式。

成本计算复用 prompt_runtime.prompt_metrics 的定价表与 compute_cost 函数。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llm.metrics.base import BaseMetricsCollector, MetricLabels

# 复用 prompt_runtime 的定价与成本计算
from prompt_runtime.prompt_metrics import compute_cost


# ------------------------------------------------------------------------------
# Data Classes
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CallRecord:
    """单次 LLM 调用的完整计费记录。"""

    request_id: str
    provider: str
    model: str
    status: str
    user: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    latency_ms: float
    timestamp: float


@dataclass
class RequestSummary:
    """单次请求摘要。"""

    request_id: str
    provider: str
    model: str
    status: str
    user: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    latency_ms: float
    timestamp: float


@dataclass
class UserSummary:
    """按用户聚合的统计。"""

    user: str
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    models: List[str]


@dataclass
class ModelSummary:
    """按模型聚合的统计。"""

    model: str
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    users: List[str]


@dataclass
class GlobalSummary:
    """全局聚合统计。"""

    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    by_user: Dict[str, UserSummary]
    by_model: Dict[str, ModelSummary]


# ------------------------------------------------------------------------------
# Token Accounting Collector
# ------------------------------------------------------------------------------


class TokenAccountingCollector(BaseMetricsCollector):
    """Token 计费收集器。

    线程安全：所有写操作受 _lock 保护；读操作在持有锁时完成副本。
    """

    def __init__(self, max_records: int = 10_000) -> None:
        self._max_records = max_records
        self._records: Dict[str, CallRecord] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # BaseMetricsCollector interface
    # ------------------------------------------------------------------

    def record(
        self,
        labels: MetricLabels,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """记录一次 LLM 调用。"""
        rid = request_id or uuid.uuid4().hex[:16]
        total_tokens = prompt_tokens + completion_tokens
        # 若未传入 cost，则自动计算
        if cost == 0.0 and prompt_tokens + completion_tokens > 0:
            cost = compute_cost(labels.model, prompt_tokens, completion_tokens)

        record = CallRecord(
            request_id=rid,
            provider=labels.provider,
            model=labels.model,
            status=labels.status,
            user=labels.user,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=round(cost, 6),
            latency_ms=round(latency_ms, 3),
            timestamp=time.time(),
        )

        with self._lock:
            if len(self._records) >= self._max_records:
                # 驱逐最老的记录
                oldest = min(self._records, key=lambda k: self._records[k].timestamp)
                del self._records[oldest]
            self._records[rid] = record

    def observe_request_duration(
        self,
        labels: MetricLabels,
        duration_ms: float,
    ) -> None:
        """记录请求耗时（已合并到 record 中，此处无额外操作）。"""
        pass

    def increment_request_total(
        self,
        labels: MetricLabels,
    ) -> None:
        """记录请求总数（已合并到 record 中，此处无额外操作）。"""
        pass

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------

    def get_by_request(self, request_id: str) -> Optional[RequestSummary]:
        """按 request_id 查询单次调用明细。"""
        with self._lock:
            r = self._records.get(request_id)
        if r is None:
            return None
        return self._record_to_request_summary(r)

    def get_by_user(self, user: str) -> UserSummary:
        """按 user 聚合统计。"""
        with self._lock:
            records = [r for r in self._records.values() if r.user == user]
        return self._aggregate_user(user, records)

    def get_by_model(self, model: str) -> ModelSummary:
        """按 model 聚合统计。"""
        with self._lock:
            records = [r for r in self._records.values() if r.model == model]
        return self._aggregate_model(model, records)

    def get_summary(self) -> GlobalSummary:
        """全局聚合统计。"""
        with self._lock:
            records = list(self._records.values())
        return self._aggregate_global(records)

    def list_requests(
        self,
        user: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[RequestSummary]:
        """按条件筛选请求列表，默认按时间倒序。"""
        with self._lock:
            records = list(self._records.values())

        if user is not None:
            records = [r for r in records if r.user == user]
        if model is not None:
            records = [r for r in records if r.model == model]
        if status is not None:
            records = [r for r in records if r.status == status]

        records = sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]
        return [self._record_to_request_summary(r) for r in records]

    def reset(self) -> None:
        """清空所有记录。"""
        with self._lock:
            self._records.clear()

    # ------------------------------------------------------------------
    # Metrics API output
    # ------------------------------------------------------------------

    def expose_metrics(self) -> str:
        """输出 Prometheus OpenMetrics 文本格式。"""
        with self._lock:
            records = list(self._records.values())

        lines: List[str] = []
        lines.append("# HELP llm_prompt_tokens_total Total prompt tokens")
        lines.append("# TYPE llm_prompt_tokens_total counter")
        lines.append("# HELP llm_completion_tokens_total Total completion tokens")
        lines.append("# TYPE llm_completion_tokens_total counter")
        lines.append("# HELP llm_total_tokens_total Total tokens")
        lines.append("# TYPE llm_total_tokens_total counter")
        lines.append("# HELP llm_cost_total Total cost in USD")
        lines.append("# TYPE llm_cost_total counter")
        lines.append("# HELP llm_request_duration_ms Request duration in milliseconds")
        lines.append("# TYPE llm_request_duration_ms summary")
        lines.append("# HELP llm_requests_total Total number of requests")
        lines.append("# TYPE llm_requests_total counter")

        # 按 (provider, model, user, status) 分组聚合
        def _group_key(r: CallRecord) -> tuple:
            return (r.provider, r.model, r.user or "anonymous", r.status)

        groups: Dict[tuple, List[CallRecord]] = {}
        for r in records:
            groups.setdefault(_group_key(r), []).append(r)

        for (provider, model, user, status), grp in sorted(groups.items()):
            labels_str = (
                f'provider="{provider}",model="{model}",'
                f'user="{user}",status="{status}"'
            )
            prompt_tokens = sum(r.prompt_tokens for r in grp)
            completion_tokens = sum(r.completion_tokens for r in grp)
            total_tokens = sum(r.total_tokens for r in grp)
            total_cost = sum(r.cost for r in grp)
            total_latency = sum(r.latency_ms for r in grp)
            count = len(grp)

            lines.append(f"llm_prompt_tokens_total{{{labels_str}}} {prompt_tokens}")
            lines.append(f"llm_completion_tokens_total{{{labels_str}}} {completion_tokens}")
            lines.append(f"llm_total_tokens_total{{{labels_str}}} {total_tokens}")
            lines.append(f"llm_cost_total{{{labels_str}}} {total_cost:.6f}")
            lines.append(f"llm_request_duration_ms_sum{{{labels_str}}} {total_latency:.3f}")
            lines.append(f"llm_request_duration_ms_count{{{labels_str}}} {count}")
            lines.append(f"llm_requests_total{{{labels_str}}} {count}")

        return "\n".join(lines)

    def to_json(self) -> Dict[str, Any]:
        """输出 JSON 格式的全局统计。"""
        summary = self.get_summary()
        return {
            "total_requests": summary.total_requests,
            "total_prompt_tokens": summary.total_prompt_tokens,
            "total_completion_tokens": summary.total_completion_tokens,
            "total_tokens": summary.total_tokens,
            "total_cost_usd": summary.total_cost,
            "avg_latency_ms": summary.avg_latency_ms,
            "by_user": {
                u: {
                    "total_requests": s.total_requests,
                    "total_prompt_tokens": s.total_prompt_tokens,
                    "total_completion_tokens": s.total_completion_tokens,
                    "total_tokens": s.total_tokens,
                    "total_cost_usd": s.total_cost,
                    "avg_latency_ms": s.avg_latency_ms,
                    "models": s.models,
                }
                for u, s in summary.by_user.items()
            },
            "by_model": {
                m: {
                    "total_requests": s.total_requests,
                    "total_prompt_tokens": s.total_prompt_tokens,
                    "total_completion_tokens": s.total_completion_tokens,
                    "total_tokens": s.total_tokens,
                    "total_cost_usd": s.total_cost,
                    "avg_latency_ms": s.avg_latency_ms,
                    "users": s.users,
                }
                for m, s in summary.by_model.items()
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_request_summary(r: CallRecord) -> RequestSummary:
        return RequestSummary(
            request_id=r.request_id,
            provider=r.provider,
            model=r.model,
            status=r.status,
            user=r.user,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            cost=r.cost,
            latency_ms=r.latency_ms,
            timestamp=r.timestamp,
        )

    @staticmethod
    def _aggregate_user(user: str, records: List[CallRecord]) -> UserSummary:
        if not records:
            return UserSummary(
                user=user,
                total_requests=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                total_cost=0.0,
                avg_latency_ms=0.0,
                models=[],
            )
        total_latency = sum(r.latency_ms for r in records)
        models = sorted({r.model for r in records})
        return UserSummary(
            user=user,
            total_requests=len(records),
            total_prompt_tokens=sum(r.prompt_tokens for r in records),
            total_completion_tokens=sum(r.completion_tokens for r in records),
            total_tokens=sum(r.total_tokens for r in records),
            total_cost=round(sum(r.cost for r in records), 6),
            avg_latency_ms=round(total_latency / len(records), 3),
            models=models,
        )

    @staticmethod
    def _aggregate_model(model: str, records: List[CallRecord]) -> ModelSummary:
        if not records:
            return ModelSummary(
                model=model,
                total_requests=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                total_cost=0.0,
                avg_latency_ms=0.0,
                users=[],
            )
        total_latency = sum(r.latency_ms for r in records)
        users = sorted({r.user for r in records if r.user})
        return ModelSummary(
            model=model,
            total_requests=len(records),
            total_prompt_tokens=sum(r.prompt_tokens for r in records),
            total_completion_tokens=sum(r.completion_tokens for r in records),
            total_tokens=sum(r.total_tokens for r in records),
            total_cost=round(sum(r.cost for r in records), 6),
            avg_latency_ms=round(total_latency / len(records), 3),
            users=users,
        )

    @classmethod
    def _aggregate_global(cls, records: List[CallRecord]) -> GlobalSummary:
        if not records:
            return GlobalSummary(
                total_requests=0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                total_cost=0.0,
                avg_latency_ms=0.0,
                by_user={},
                by_model={},
            )

        total_latency = sum(r.latency_ms for r in records)
        by_user: Dict[str, List[CallRecord]] = {}
        by_model: Dict[str, List[CallRecord]] = {}
        for r in records:
            by_user.setdefault(r.user or "anonymous", []).append(r)
            by_model.setdefault(r.model, []).append(r)

        return GlobalSummary(
            total_requests=len(records),
            total_prompt_tokens=sum(r.prompt_tokens for r in records),
            total_completion_tokens=sum(r.completion_tokens for r in records),
            total_tokens=sum(r.total_tokens for r in records),
            total_cost=round(sum(r.cost for r in records), 6),
            avg_latency_ms=round(total_latency / len(records), 3),
            by_user={
                u: cls._aggregate_user(u, rs) for u, rs in by_user.items()
            },
            by_model={
                m: cls._aggregate_model(m, rs) for m, rs in by_model.items()
            },
        )

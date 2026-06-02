"""应用级指标收集器。

提供线程安全的内存指标存储，支持：
  - HTTP 请求计数与延迟
  - LLM 调用计数与延迟（预留接口）
  - Celery 任务计数
  - 错误计数

设计约束：
  - 不引入外部 metrics 库（如 prometheus_client）。
  - 所有数据结构设上限，防止内存泄漏。
  - 使用 threading.Lock 保证并发安全。
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricsSnapshot:
    """指标快照（可序列化为 JSON）。"""

    http_requests: dict[str, int] = field(default_factory=dict)
    http_latency_ms: dict[str, dict[str, float]] = field(default_factory=dict)
    llm_calls: dict[str, int] = field(default_factory=dict)
    llm_latency_ms: dict[str, dict[str, float]] = field(default_factory=dict)
    celery_tasks: dict[str, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    collected_at: Optional[str] = None


class MetricsCollector:
    """线程安全的内存指标收集器。"""

    # 各数据结构的保留上限
    _MAX_LATENCY_ENTRIES = 1000
    _MAX_HTTP_PATHS = 200
    _MAX_LLM_KEYS = 100
    _MAX_CELERY_KEYS = 100
    _MAX_ERROR_CODES = 50

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # HTTP 指标
        self._http_requests: Counter = Counter()
        self._http_latency: dict[str, list[float]] = defaultdict(list)

        # LLM 指标（预留，供 Gateway 桥接使用）
        self._llm_calls: Counter = Counter()
        self._llm_latency: dict[str, list[float]] = defaultdict(list)

        # Celery 指标
        self._celery_tasks: Counter = Counter()

        # 错误指标
        self._errors: Counter = Counter()

    # ------------------------------------------------------------------
    # HTTP 指标
    # ------------------------------------------------------------------

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
    ) -> None:
        """记录一次 HTTP 请求。"""
        key = f"{method}:{path}:{status_code}"
        with self._lock:
            self._http_requests[key] += 1
            latencies = self._http_latency[path]
            latencies.append(latency_ms)
            if len(latencies) > self._MAX_LATENCY_ENTRIES:
                latencies.pop(0)
            # 限制 path 数量
            if len(self._http_latency) > self._MAX_HTTP_PATHS:
                oldest = next(iter(self._http_latency))
                del self._http_latency[oldest]

    # ------------------------------------------------------------------
    # LLM 指标
    # ------------------------------------------------------------------

    def record_llm_call(
        self,
        provider: str,
        model: str,
        status: str,
        latency_ms: float,
    ) -> None:
        """记录一次 LLM 调用。"""
        key = f"{provider}:{model}:{status}"
        with self._lock:
            self._llm_calls[key] += 1
            latencies = self._llm_latency[provider]
            latencies.append(latency_ms)
            if len(latencies) > self._MAX_LATENCY_ENTRIES:
                latencies.pop(0)
            if len(self._llm_latency) > self._MAX_LLM_KEYS:
                oldest = next(iter(self._llm_latency))
                del self._llm_latency[oldest]

    # ------------------------------------------------------------------
    # Celery 指标
    # ------------------------------------------------------------------

    def record_celery_task(
        self,
        task_name: str,
        status: str,
    ) -> None:
        """记录一次 Celery 任务执行。"""
        key = f"{task_name}:{status}"
        with self._lock:
            self._celery_tasks[key] += 1
            if len(self._celery_tasks) > self._MAX_CELERY_KEYS:
                # Counter 不支持直接 pop，转换为 dict 再重建
                items = list(self._celery_tasks.items())[-self._MAX_CELERY_KEYS:]
                self._celery_tasks = Counter(dict(items))

    # ------------------------------------------------------------------
    # 错误指标
    # ------------------------------------------------------------------

    def record_error(self, code: str) -> None:
        """记录一次错误（按错误码聚合）。"""
        with self._lock:
            self._errors[code] += 1
            if len(self._errors) > self._MAX_ERROR_CODES:
                items = list(self._errors.items())[-self._MAX_ERROR_CODES:]
                self._errors = Counter(dict(items))

    # ------------------------------------------------------------------
    # 快照导出
    # ------------------------------------------------------------------

    def snapshot(self) -> MetricsSnapshot:
        """导出当前指标快照。"""
        from datetime import datetime, timezone

        with self._lock:
            return MetricsSnapshot(
                http_requests=dict(self._http_requests),
                http_latency_ms={
                    k: {
                        "count": len(v),
                        "avg_ms": round(sum(v) / len(v), 2) if v else 0.0,
                        "p99_ms": round(self._percentile(v, 0.99), 2) if v else 0.0,
                    }
                    for k, v in self._http_latency.items()
                },
                llm_calls=dict(self._llm_calls),
                llm_latency_ms={
                    k: {
                        "count": len(v),
                        "avg_ms": round(sum(v) / len(v), 2) if v else 0.0,
                        "p99_ms": round(self._percentile(v, 0.99), 2) if v else 0.0,
                    }
                    for k, v in self._llm_latency.items()
                },
                celery_tasks=dict(self._celery_tasks),
                errors=dict(self._errors),
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """计算百分位值（Nearest Rank 方法）。"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * percentile)
        idx = max(0, min(idx, len(sorted_data) - 1))
        return sorted_data[idx]

    # ------------------------------------------------------------------
    # Prometheus 格式导出（零外部依赖）
    # ------------------------------------------------------------------

    def to_prometheus(self) -> str:
        """导出为 Prometheus / OpenMetrics 文本格式。

        所有时间指标统一转换为秒（Prometheus 惯例）。
        """
        lines: list[str] = []

        with self._lock:
            # ---- HTTP Requests Counter ----
            lines.append("# HELP vcw_http_requests_total Total HTTP requests")
            lines.append("# TYPE vcw_http_requests_total counter")
            for key, count in self._http_requests.items():
                method, path, status = key.split(":", 2)
                safe_path = self._escape_label(path)
                lines.append(
                    f'vcw_http_requests_total{{method="{method}",path="{safe_path}",status="{status}"}} {count}'
                )

            # ---- HTTP Latency Summary ----
            lines.append("# HELP vcw_http_request_duration_seconds HTTP request latency")
            lines.append("# TYPE vcw_http_request_duration_seconds summary")
            for path, latencies in self._http_latency.items():
                if not latencies:
                    continue
                safe_path = self._escape_label(path)
                total_s = sum(latencies) / 1000.0
                lines.append(
                    f'vcw_http_request_duration_seconds_count{{path="{safe_path}"}} {len(latencies)}'
                )
                lines.append(
                    f'vcw_http_request_duration_seconds_sum{{path="{safe_path}"}} {total_s:.6f}'
                )
                p99 = self._percentile(latencies, 0.99) / 1000.0
                lines.append(
                    f'vcw_http_request_duration_seconds{{path="{safe_path}",quantile="0.99"}} {p99:.6f}'
                )

            # ---- LLM Calls Counter ----
            lines.append("# HELP vcw_llm_calls_total Total LLM calls")
            lines.append("# TYPE vcw_llm_calls_total counter")
            for key, count in self._llm_calls.items():
                provider, model, status = key.split(":", 2)
                lines.append(
                    f'vcw_llm_calls_total{{provider="{provider}",model="{model}",status="{status}"}} {count}'
                )

            # ---- LLM Latency Summary ----
            lines.append("# HELP vcw_llm_request_duration_seconds LLM request latency")
            lines.append("# TYPE vcw_llm_request_duration_seconds summary")
            for provider, latencies in self._llm_latency.items():
                if not latencies:
                    continue
                total_s = sum(latencies) / 1000.0
                lines.append(
                    f'vcw_llm_request_duration_seconds_count{{provider="{provider}"}} {len(latencies)}'
                )
                lines.append(
                    f'vcw_llm_request_duration_seconds_sum{{provider="{provider}"}} {total_s:.6f}'
                )
                p99 = self._percentile(latencies, 0.99) / 1000.0
                lines.append(
                    f'vcw_llm_request_duration_seconds{{provider="{provider}",quantile="0.99"}} {p99:.6f}'
                )

            # ---- Celery Tasks Counter ----
            lines.append("# HELP vcw_celery_tasks_total Total Celery tasks")
            lines.append("# TYPE vcw_celery_tasks_total counter")
            for key, count in self._celery_tasks.items():
                task_name, status = key.rsplit(":", 1)
                lines.append(
                    f'vcw_celery_tasks_total{{task_name="{task_name}",status="{status}"}} {count}'
                )

            # ---- Errors Counter ----
            lines.append("# HELP vcw_errors_total Total errors")
            lines.append("# TYPE vcw_errors_total counter")
            for code, count in self._errors.items():
                lines.append(
                    f'vcw_errors_total{{code="{code}"}} {count}'
                )

        return "\n".join(lines) + "\n"

    @staticmethod
    def _escape_label(value: str) -> str:
        """转义 label 值中的特殊字符（反斜杠和双引号）。"""
        return value.replace("\\", "\\\\").replace('"', '\\"')


# 全局单例（供无请求上下文场景使用，如 Celery worker）
_global_collector: Optional[MetricsCollector] = None
_global_lock = threading.Lock()


def get_global_collector() -> MetricsCollector:
    """获取全局 MetricsCollector 单例。"""
    global _global_collector
    if _global_collector is None:
        with _global_lock:
            if _global_collector is None:
                _global_collector = MetricsCollector()
    return _global_collector


def set_global_collector(collector: MetricsCollector) -> None:
    """设置全局 MetricsCollector 单例（通常在应用初始化时调用）。"""
    global _global_collector
    with _global_lock:
        _global_collector = collector

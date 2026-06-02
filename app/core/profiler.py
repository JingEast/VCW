"""轻量级性能分析器。

提供函数调用耗时记录与慢调用分析。
设计约束：
  - 线程安全（threading.Lock）。
  - 内存有上限（默认保留最近 1000 条记录）。
  - 零外部依赖。
  - 默认仅在 app.debug=True 时通过中间件自动启用。
  - 支持慢查询阈值报警（默认 1000ms）。
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProfileRecord:
    """单次性能分析记录。"""

    name: str
    duration_ms: float
    timestamp: float
    meta: dict[str, Any] = field(default_factory=dict)


class Profiler:
    """线程安全的内存性能分析器。"""

    _MAX_RECORDS = 1000
    _DEFAULT_SLOW_THRESHOLD_MS = 1000.0
    _MEMORY_ALERT_THRESHOLD_KB = 512.0

    def __init__(
        self,
        max_records: int = _MAX_RECORDS,
        slow_threshold_ms: float = _DEFAULT_SLOW_THRESHOLD_MS,
        memory_alert_threshold_kb: float = _MEMORY_ALERT_THRESHOLD_KB,
    ) -> None:
        self._max_records = max_records
        self.slow_threshold_ms = slow_threshold_ms
        self._memory_alert_threshold_kb = memory_alert_threshold_kb
        self._lock = threading.RLock()
        self._records: list[ProfileRecord] = []

    def memory_estimate_kb(self) -> float:
        """估算当前内存占用（KB，近似值）。"""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return 0.0
            # ProfileRecord 基础开销 + name/meta 变量部分
            sample = self._records[0]
            base = 184  # sys.getsizeof({}) baseline for similar dict
            name_len = len(sample.name.encode("utf-8"))
            meta_overhead = sum(
                len(str(k).encode("utf-8")) + len(str(v).encode("utf-8"))
                for k, v in sample.meta.items()
            )
            record_size = base + name_len + meta_overhead
            return round(total * record_size / 1024, 2)

    def record(
        self,
        name: str,
        duration_ms: float,
        **meta: Any,
    ) -> None:
        """记录一次调用耗时。

        若 duration_ms 超过 slow_threshold_ms，自动记录警告日志。
        """
        with self._lock:
            self._records.append(
                ProfileRecord(
                    name=name,
                    duration_ms=duration_ms,
                    timestamp=time.perf_counter(),
                    meta=meta,
                )
            )
            if len(self._records) > self._max_records:
                self._records.pop(0)
        # 在锁外执行日志，避免 I/O 阻塞临界区
        if duration_ms > self.slow_threshold_ms:
            logger.warning(
                "[SLOW_QUERY] name=%s duration_ms=%.2f threshold_ms=%.2f meta=%s",
                name,
                duration_ms,
                self.slow_threshold_ms,
                meta,
            )
            # 同步到 MetricsCollector（供 Prometheus / Grafana 消费）
            try:
                from app.core.metrics import get_global_collector

                collector = get_global_collector()
                # 优先尝试从当前 Flask app 获取 metrics（避免全局单例被外部覆盖）
                try:
                    from flask import current_app

                    app_collector = getattr(current_app, "metrics", None)
                    if app_collector is not None:
                        collector = app_collector
                except Exception:
                    pass
                collector.record_slow_query(name)
            except Exception:
                pass

    def slowest(self, n: int = 10) -> list[ProfileRecord]:
        """返回最慢的 N 条记录（按 duration_ms 降序）。"""
        with self._lock:
            return sorted(self._records, key=lambda r: r.duration_ms, reverse=True)[:n]

    def slow_queries(
        self,
        threshold_ms: Optional[float] = None,
    ) -> list[ProfileRecord]:
        """返回超过阈值的所有慢查询记录（按 duration_ms 降序）。

        Args:
            threshold_ms: 覆盖默认 slow_threshold_ms 的阈值。
        """
        threshold = threshold_ms if threshold_ms is not None else self.slow_threshold_ms
        with self._lock:
            return sorted(
                [r for r in self._records if r.duration_ms > threshold],
                key=lambda r: r.duration_ms,
                reverse=True,
            )

    def snapshot(self) -> dict[str, Any]:
        """导出当前分析快照。"""
        with self._lock:
            total = len(self._records)
            mem_kb = self.memory_estimate_kb()
            if total == 0:
                return {"count": 0, "memory_kb": mem_kb, "records": []}
            durations = [r.duration_ms for r in self._records]
            by_name: dict[str, list[float]] = {}
            for r in self._records:
                by_name.setdefault(r.name, []).append(r.duration_ms)
            slow_count = len([d for d in durations if d > self.slow_threshold_ms])
            return {
                "count": total,
                "memory_kb": mem_kb,
                "avg_ms": round(sum(durations) / total, 2),
                "max_ms": round(max(durations), 2),
                "min_ms": round(min(durations), 2),
                "slow_threshold_ms": round(self.slow_threshold_ms, 2),
                "slow_count": slow_count,
                "by_name": {
                    name: {
                        "count": len(vals),
                        "avg_ms": round(sum(vals) / len(vals), 2),
                        "max_ms": round(max(vals), 2),
                    }
                    for name, vals in by_name.items()
                },
                "slowest": [
                    {
                        "name": r.name,
                        "duration_ms": round(r.duration_ms, 2),
                        "meta": r.meta,
                    }
                    for r in self.slowest(10)
                ],
                "slow_queries": [
                    {
                        "name": r.name,
                        "duration_ms": round(r.duration_ms, 2),
                        "meta": r.meta,
                    }
                    for r in self.slow_queries()
                ],
            }

    def clear(self) -> None:
        """清空所有记录。"""
        with self._lock:
            self._records.clear()


def profile(
    name: Optional[str] = None,
    profiler: Optional[Profiler] = None,
    slow_threshold_ms: Optional[float] = None,
) -> Callable:
    """装饰器：自动记录被装饰函数的调用耗时。

    Args:
        name: 自定义记录名称，默认为函数全限定名。
        profiler: 显式指定 Profiler 实例；None 时尝试从 Flask app 获取。
        slow_threshold_ms: 覆盖 profiler 默认阈值的慢查询阈值（毫秒）。
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _profiler = profiler
            if _profiler is None:
                try:
                    from flask import current_app

                    _profiler = getattr(current_app, "profiler", None)
                except Exception:
                    pass
            if _profiler is None:
                _profiler = get_global_profiler()

            record_name = name or func.__name__
            t0 = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - t0) * 1000
                _profiler.record(record_name, duration_ms)
                threshold = slow_threshold_ms if slow_threshold_ms is not None else _profiler.slow_threshold_ms
                if duration_ms > threshold:
                    logger.warning(
                        "[SLOW_QUERY_DECORATOR] %s took %.2fms (threshold: %.2fms)",
                        record_name,
                        duration_ms,
                        threshold,
                    )

        return wrapper

    return decorator


# 全局单例（供无 Flask 上下文场景使用）
_global_profiler: Optional[Profiler] = None
_global_lock = threading.Lock()


def get_global_profiler() -> Profiler:
    """获取全局 Profiler 单例。"""
    global _global_profiler
    if _global_profiler is None:
        with _global_lock:
            if _global_profiler is None:
                _global_profiler = Profiler()
    return _global_profiler


def set_global_profiler(profiler: Profiler) -> None:
    """设置全局 Profiler 单例。"""
    global _global_profiler
    with _global_lock:
        _global_profiler = profiler

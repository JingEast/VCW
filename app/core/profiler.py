"""轻量级性能分析器。

提供函数调用耗时记录与慢调用分析。
设计约束：
  - 线程安全（threading.Lock）。
  - 内存有上限（默认保留最近 1000 条记录）。
  - 零外部依赖。
  - 默认仅在 app.debug=True 时通过中间件自动启用。
"""

from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


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

    def __init__(self, max_records: int = _MAX_RECORDS) -> None:
        self._max_records = max_records
        self._lock = threading.RLock()
        self._records: list[ProfileRecord] = []

    def record(
        self,
        name: str,
        duration_ms: float,
        **meta: Any,
    ) -> None:
        """记录一次调用耗时。"""
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

    def slowest(self, n: int = 10) -> list[ProfileRecord]:
        """返回最慢的 N 条记录（按 duration_ms 降序）。"""
        with self._lock:
            return sorted(self._records, key=lambda r: r.duration_ms, reverse=True)[:n]

    def snapshot(self) -> dict[str, Any]:
        """导出当前分析快照。"""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return {"count": 0, "records": []}
            durations = [r.duration_ms for r in self._records]
            by_name: dict[str, list[float]] = {}
            for r in self._records:
                by_name.setdefault(r.name, []).append(r.duration_ms)
            return {
                "count": total,
                "avg_ms": round(sum(durations) / total, 2),
                "max_ms": round(max(durations), 2),
                "min_ms": round(min(durations), 2),
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
            }

    def clear(self) -> None:
        """清空所有记录。"""
        with self._lock:
            self._records.clear()


def profile(
    name: Optional[str] = None,
    profiler: Optional[Profiler] = None,
) -> Callable:
    """装饰器：自动记录被装饰函数的调用耗时。

    Args:
        name: 自定义记录名称，默认为函数全限定名。
        profiler: 显式指定 Profiler 实例；None 时尝试从 Flask app 获取。
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

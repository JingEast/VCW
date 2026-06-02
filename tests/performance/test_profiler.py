"""性能分析器测试。"""

from __future__ import annotations

import threading
import time


class TestProfiler:
    """验证 Profiler 核心功能。"""

    def test_record_and_slowest(self):
        """记录后 slowest 应返回按耗时降序排列的记录。"""
        from app.core.profiler import Profiler

        profiler = Profiler()
        profiler.record("fast", 10.0)
        profiler.record("slow", 100.0)
        profiler.record("medium", 50.0)

        slowest = profiler.slowest(2)
        assert len(slowest) == 2
        assert slowest[0].name == "slow"
        assert slowest[0].duration_ms == 100.0
        assert slowest[1].name == "medium"

    def test_max_records_limit(self):
        """超过上限时最早记录应被移除。"""
        from app.core.profiler import Profiler

        profiler = Profiler(max_records=5)
        for i in range(10):
            profiler.record(f"task-{i}", float(i))

        snapshot = profiler.snapshot()
        assert snapshot["count"] == 5

    def test_snapshot_stats(self):
        """快照应包含正确的统计信息。"""
        from app.core.profiler import Profiler

        profiler = Profiler()
        profiler.record("a", 10.0)
        profiler.record("a", 20.0)
        profiler.record("b", 30.0)

        snap = profiler.snapshot()
        assert snap["count"] == 3
        assert snap["avg_ms"] == 20.0
        assert snap["max_ms"] == 30.0
        assert snap["min_ms"] == 10.0
        assert snap["by_name"]["a"]["count"] == 2
        assert snap["by_name"]["a"]["avg_ms"] == 15.0

    def test_clear(self):
        """清空后记录应为空。"""
        from app.core.profiler import Profiler

        profiler = Profiler()
        profiler.record("x", 1.0)
        profiler.clear()
        assert profiler.snapshot()["count"] == 0

    def test_thread_safety(self):
        """并发写入不应丢失数据。"""
        from app.core.profiler import Profiler

        profiler = Profiler()

        def worker():
            for _ in range(100):
                profiler.record("concurrent", 1.0)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert profiler.snapshot()["count"] == 1000


class TestProfileDecorator:
    """验证 @profile 装饰器。"""

    def test_decorator_records_duration(self, app):
        """装饰器应自动记录函数调用耗时。"""
        from app.core.profiler import profile, Profiler

        profiler = Profiler()
        app.profiler = profiler  # type: ignore[attr-defined]

        @profile()
        def slow_func():
            time.sleep(0.01)
            return 42

        result = slow_func()
        assert result == 42
        snap = profiler.snapshot()
        assert snap["count"] >= 1
        assert "slow_func" in snap["by_name"]

    def test_decorator_with_custom_name(self, app):
        """装饰器应支持自定义记录名称。"""
        from app.core.profiler import profile, Profiler

        profiler = Profiler()
        app.profiler = profiler  # type: ignore[attr-defined]

        @profile(name="custom_name")
        def my_func():
            return 1

        my_func()
        snap = profiler.snapshot()
        assert "custom_name" in snap["by_name"]


class TestProfilerMiddleware:
    """验证 Flask profiling 中间件端到端行为。"""

    def test_profiler_attached_to_app(self, app):
        """create_app 后 app 应挂载 profiler 属性。"""
        from app.core.profiler import Profiler

        assert hasattr(app, "profiler")
        assert isinstance(app.profiler, Profiler)

    def test_request_recorded_when_debug(self, app, client):
        """debug 模式下请求应被记录到 profiler。"""
        app.debug = True
        client.get("/")
        snap = app.profiler.snapshot()
        assert snap["count"] >= 1
        assert any("http:GET" in r["name"] for r in snap["slowest"])

    def test_debug_profile_endpoint_returns_json(self, app, client):
        """/debug/profile 端点应返回 JSON（仅 debug 模式）。"""
        app.debug = True
        client.get("/")
        response = client.get("/debug/profile")
        assert response.status_code == 200
        data = response.get_json()
        assert "count" in data
        assert "slowest" in data

    def test_debug_profile_clear_works(self, app, client):
        """/debug/profile/clear 应清空记录。"""
        app.debug = True
        client.get("/")
        response = client.post("/debug/profile/clear")
        assert response.status_code == 200
        assert app.profiler.snapshot()["count"] == 0

"""Metrics 收集器测试。"""

from __future__ import annotations

import threading


class TestMetricsCollector:
    """验证 MetricsCollector 线程安全与数据正确性。"""

    def test_record_http_request(self):
        """记录 HTTP 请求后计数器应增加。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.record_http_request("GET", "/", 200, 15.5)
        collector.record_http_request("GET", "/", 200, 25.5)
        collector.record_http_request("POST", "/api", 201, 30.0)

        snap = collector.snapshot()
        assert snap.http_requests["GET:/:200"] == 2
        assert snap.http_requests["POST:/api:201"] == 1

    def test_http_latency_aggregation(self):
        """HTTP 延迟应被聚合为 avg 与 p99。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        for i in range(10):
            collector.record_http_request("GET", "/", 200, float(i))

        snap = collector.snapshot()
        lat = snap.http_latency_ms["/"]
        assert lat["count"] == 10
        assert lat["avg_ms"] == 4.5

    def test_record_error(self):
        """记录错误后错误计数器应增加。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.record_error("NOT_FOUND")
        collector.record_error("NOT_FOUND")
        collector.record_error("BAD_REQUEST")

        snap = collector.snapshot()
        assert snap.errors["NOT_FOUND"] == 2
        assert snap.errors["BAD_REQUEST"] == 1

    def test_record_celery_task(self):
        """记录 Celery 任务后计数器应增加。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.record_celery_task("echo_task", "success")
        collector.record_celery_task("echo_task", "success")
        collector.record_celery_task("echo_task", "failed")

        snap = collector.snapshot()
        assert snap.celery_tasks["echo_task:success"] == 2
        assert snap.celery_tasks["echo_task:failed"] == 1

    def test_record_llm_call(self):
        """记录 LLM 调用后计数器与延迟应正确。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.record_llm_call("openai", "gpt-4o", "success", 1200.0)
        collector.record_llm_call("openai", "gpt-4o", "success", 800.0)

        snap = collector.snapshot()
        assert snap.llm_calls["openai:gpt-4o:success"] == 2
        assert snap.llm_latency_ms["openai"]["avg_ms"] == 1000.0

    def test_latency_max_entries_limit(self):
        """延迟列表超过上限时应自动截断。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        for i in range(1500):
            collector.record_http_request("GET", "/", 200, float(i))

        snap = collector.snapshot()
        # 上限为 1000，但 count 应显示实际存储数量
        assert snap.http_latency_ms["/"]["count"] == 1000

    def test_thread_safety(self):
        """并发写入不应丢失数据。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()

        def worker():
            for _ in range(100):
                collector.record_http_request("GET", "/", 200, 1.0)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = collector.snapshot()
        assert snap.http_requests["GET:/:200"] == 1000

    def test_snapshot_contains_timestamp(self):
        """快照应包含收集时间戳。"""
        from app.core.metrics import MetricsCollector

        collector = MetricsCollector()
        snap = collector.snapshot()
        assert snap.collected_at is not None
        assert "T" in snap.collected_at


class TestGlobalCollector:
    """验证全局 MetricsCollector 单例。"""

    def test_get_global_collector_returns_singleton(self):
        """多次获取应返回同一实例。"""
        from app.core.metrics import get_global_collector

        c1 = get_global_collector()
        c2 = get_global_collector()
        assert c1 is c2

    def test_set_global_collector_overrides(self):
        """set_global_collector 应能覆盖全局实例。"""
        from app.core.metrics import MetricsCollector, get_global_collector, set_global_collector

        new_collector = MetricsCollector()
        set_global_collector(new_collector)
        assert get_global_collector() is new_collector


class TestHttpMetricsMiddleware:
    """验证 HTTP 指标中间件端到端行为。"""

    def test_metrics_collector_attached_to_app(self, app):
        """create_app 后 app 应挂载 metrics 属性。"""
        from app.core.metrics import MetricsCollector

        assert hasattr(app, "metrics")
        assert isinstance(app.metrics, MetricsCollector)

    def test_http_request_recorded(self, client, app):
        """发起请求后指标应被记录。"""
        client.get("/")
        snap = app.metrics.snapshot()
        assert any("GET" in k for k in snap.http_requests)

    def test_error_request_recorded(self, client, app):
        """错误请求也应被记录到错误指标。"""
        client.get("/nonexistent-page-trigger-404")
        snap = app.metrics.snapshot()
        # 404 错误会被记录到 errors 中
        assert snap.errors.get("NOT_FOUND", 0) >= 1

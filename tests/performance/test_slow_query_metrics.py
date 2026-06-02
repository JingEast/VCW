"""验证 /metrics 端点暴露慢查询指标。"""


class TestSlowQueryMetrics:
    def test_metrics_includes_slow_query_counter(self, app, client):
        """慢查询计数器应出现在 Prometheus /metrics 输出中。"""
        app.metrics.record_slow_query("test_slow_endpoint")

        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.data.decode()
        assert "vcw_slow_queries_total" in text
        assert 'name="test_slow_endpoint"' in text

    def test_profiler_records_slow_query_to_metrics(self, app, client):
        """Profiler 检测到慢查询后，MetricsCollector 应同步计数。"""
        from app.core.profiler import Profiler

        profiler = Profiler(slow_threshold_ms=1.0)
        profiler.record("heavy_query", 100.0, path="/api/test")

        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.data.decode()
        assert "vcw_slow_queries_total" in text
        assert 'name="heavy_query"' in text

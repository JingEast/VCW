"""验证 /metrics 端点暴露 DB 连接池指标。"""


class TestDBPoolMetrics:
    def test_metrics_includes_pool_stats(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        text = response.data.decode()
        assert "db_pool_size" in text
        assert "db_pool_checked_in" in text
        assert "db_pool_checked_out" in text
        assert "db_pool_overflow" in text

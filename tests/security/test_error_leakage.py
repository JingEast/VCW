"""安全测试：验证异常信息不会泄漏到客户端响应中。"""

from __future__ import annotations


class TestTracebackLeakage:
    """验证 traceback 不会通过 HTTP 响应暴露。"""

    def test_500_production_hides_traceback(self, client, app):
        """生产模式 (debug=False) 下 500 错误不暴露异常详情。"""
        app.debug = False
        response = client.get("/trigger-500-format")
        data = response.get_json()

        assert response.status_code == 500
        assert data["error"]["message"] == "Internal Server Error"
        assert "sensitive details" not in data["error"]["message"]
        assert "traceback" not in str(data).lower()

    def test_500_debug_shows_error(self, client, app):
        """调试模式 (debug=True) 下 500 错误可以暴露异常信息。"""
        app.debug = True
        response = client.get("/trigger-500-debug")
        data = response.get_json()

        assert response.status_code == 500
        assert "debug mode error" in data["error"]["message"]

    def test_404_never_exposes_traceback(self, client):
        """404 响应始终不暴露 traceback。"""
        response = client.get("/nonexistent-page-12345")
        data = response.get_json()

        assert response.status_code == 404
        assert "traceback" not in str(data).lower()
        assert "exception" not in str(data).lower()

    def test_405_never_exposes_traceback(self, client):
        """405 响应始终不暴露 traceback。"""
        response = client.post("/")
        data = response.get_json()

        assert response.status_code == 405
        assert "traceback" not in str(data).lower()

    def test_bad_request_never_exposes_traceback(self, client):
        """400 响应始终不暴露 traceback。"""
        response = client.get("/trigger-400")
        data = response.get_json()

        assert response.status_code == 400
        assert "traceback" not in str(data).lower()


class TestTraceIdConsistency:
    """验证 trace_id 在所有错误响应中存在且格式正确。"""

    def test_trace_id_present_on_500(self, client, app):
        app.debug = False
        response = client.get("/trigger-500")
        data = response.get_json()

        assert "trace_id" in data
        assert len(data["trace_id"]) == 12
        assert data["trace_id"] != "-"

    def test_trace_id_present_on_404(self, client):
        response = client.get("/missing")
        data = response.get_json()

        assert "trace_id" in data
        assert len(data["trace_id"]) == 12

    def test_trace_id_unique_per_request(self, client, app):
        app.debug = False
        resp1 = client.get("/trigger-500")
        resp2 = client.get("/trigger-500")

        tid1 = resp1.get_json()["trace_id"]
        tid2 = resp2.get_json()["trace_id"]

        assert tid1 != tid2

"""
全局错误处理器测试

验证 Prompt D 中注册的全局错误处理器：
  - 所有异常返回统一 JSON 格式
  - 包含 12 字符 trace_id
  - 日志记录正确（不直接验证日志文件，仅验证响应格式）
"""



class Test404Handler:
    """404 Not Found 错误测试"""

    def test_404_returns_json(self, client):
        """访问不存在的页面返回 JSON"""
        response = client.get("/this-page-does-not-exist")
        assert response.status_code == 404
        assert response.content_type.startswith("application/json")

    def test_404_response_format(self, client):
        """404 响应包含 success/error/trace_id 字段"""
        response = client.get("/nonexistent")
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Not Found"
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12


class Test405Handler:
    """405 Method Not Allowed 错误测试"""

    def test_405_returns_json(self, client):
        """POST 到仅支持 GET 的路由返回 JSON"""
        response = client.post("/")
        assert response.status_code == 405
        assert response.content_type.startswith("application/json")

    def test_405_response_format(self, client):
        """405 响应包含 trace_id"""
        response = client.post("/trends")
        data = response.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert data["error"]["message"] == "Method Not Allowed"
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12


class Test500Handler:
    """500 Internal Server Error 错误测试"""

    def test_500_returns_json(self, client):
        """未处理异常返回 JSON"""
        response = client.get("/trigger-500")
        assert response.status_code == 500
        assert response.content_type.startswith("application/json")

    def test_500_response_format(self, client, app):
        """500 响应在 debug=False 时隐藏具体异常，包含 trace_id"""
        original_debug = app.debug
        app.debug = False

        response = client.get("/trigger-500-format")
        data = response.get_json()

        assert data["success"] is False
        assert data["error"]["code"] == "UNHANDLED_EXCEPTION"
        assert data["error"]["message"] == "Internal Server Error"
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12
        # 生产环境不应暴露具体异常信息
        assert "sensitive details" not in data["error"]["message"]

        app.debug = original_debug

    def test_500_includes_trace_id_in_debug(self, client, app):
        """debug=True 时返回具体异常信息，但仍包含 trace_id"""
        app.debug = True

        response = client.get("/trigger-500-debug")
        data = response.get_json()

        assert data["success"] is False
        assert "debug mode error" in data["error"]["message"]
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12


class TestBadRequestHandler:
    """400 Bad Request 错误测试"""

    def test_400_returns_json(self, client):
        """构造 BadRequest 返回 JSON"""
        response = client.get("/trigger-400")
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12

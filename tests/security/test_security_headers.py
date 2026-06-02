"""安全测试：验证安全响应头与 CORS 配置。"""

from __future__ import annotations


class TestSecurityHeaders:
    """验证全局安全响应头。"""

    def test_api_has_x_content_type_options(self, client):
        response = client.get("/api/v1/model/status")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_api_has_x_frame_options(self, client):
        response = client.get("/api/v1/model/status")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_api_has_x_xss_protection(self, client):
        response = client.get("/api/v1/model/status")
        assert "1; mode=block" in response.headers.get("X-XSS-Protection", "")

    def test_api_has_referrer_policy(self, client):
        response = client.get("/api/v1/model/status")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_api_has_permissions_policy(self, client):
        response = client.get("/api/v1/model/status")
        assert "geolocation=()" in response.headers.get("Permissions-Policy", "")

    def test_api_has_csp(self, client):
        response = client.get("/api/v1/model/status")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_html_has_cache_control_no_store(self, client):
        response = client.get("/")
        assert response.headers.get("Cache-Control") == "no-store, must-revalidate"


class TestPathTraversalProtection:
    """验证 /api/v1/files/preview 路径遍历防护。"""

    def test_preview_rejects_absolute_path(self, client):
        response = client.get("/api/v1/files/preview/C:/Windows/System32/drivers/etc/hosts")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_PATH"

    def test_preview_rejects_dot_dot(self, client):
        response = client.get("/api/v1/files/preview/../../../etc/passwd")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_PATH"

    def test_preview_rejects_disallowed_extension(self, client):
        response = client.get("/api/v1/files/preview/data/prompts_custom.py")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_FILE_TYPE"

    def test_preview_rejects_disallowed_directory(self, client):
        # .py 扩展名会先触发 INVALID_FILE_TYPE，使用 .txt 测试目录限制
        response = client.get("/api/v1/files/preview/app/config.txt")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_PATH"

    def test_preview_allows_safe_file(self, client):
        response = client.get("/api/v1/files/preview/data/prompts_custom.json")
        assert response.status_code in (200, 404)


class TestInputSanitization:
    """验证 API 输入长度限制与清理。"""

    def test_generate_stream_rejects_very_long_topic(self, client):
        """超长主题应被截断处理。"""
        long_topic = "A" * 1000
        response = client.get(f"/api/v1/generate/stream?topic={long_topic}")
        # 即使超长也应返回 200（SSE 流）或 400（如果拒绝）
        assert response.status_code in (200, 400)

    def test_generate_async_rejects_empty_topic(self, client):
        response = client.post("/api/v1/generate/async", json={"topic": "  "})
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_generate_batch_rejects_too_many_angles(self, client):
        angles = [f"angle-{i}" for i in range(20)]
        response = client.post(
            "/api/v1/generate/batch/async",
            json={"topic": "test", "angles": angles},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

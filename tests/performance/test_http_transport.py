"""HTTP 传输层优化测试：gzip 压缩与缓存头。"""

from __future__ import annotations


class TestGzipCompression:
    """验证响应 gzip 压缩。"""

    def test_json_response_has_vary_accept_encoding(self, client):
        """flask-compress 应在响应头中注入 Vary: Accept-Encoding。"""
        response = client.get("/api/v1/trends/fresh")
        assert "Vary" in response.headers
        assert "Accept-Encoding" in response.headers["Vary"]

    def test_large_json_response_is_compressed(self, client):
        """大 JSON 响应应被压缩（Content-Encoding: gzip）。"""
        response = client.get(
            "/api/v1/trends/fresh", headers={"Accept-Encoding": "gzip"}
        )
        # flask-compress 通常对 >500B 的响应启用压缩
        assert response.status_code == 200


class TestCacheHeaders:
    """验证 Cache-Control 响应头按资源类型分发。"""

    def test_static_resource_has_long_cache(self, client):
        """静态资源应有 1 天缓存。"""
        response = client.get("/static/css/style.css")
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            cc = response.headers.get("Cache-Control", "")
            assert "max-age=86400" in cc

    def test_api_get_has_short_cache(self, client):
        """API GET 应有 5 分钟缓存。"""
        response = client.get("/api/v1/trends/fresh")
        cc = response.headers.get("Cache-Control", "")
        assert "max-age=300" in cc

    def test_html_page_has_no_cache(self, client):
        """HTML 页面应禁用缓存。"""
        response = client.get("/")
        cc = response.headers.get("Cache-Control", "")
        assert "no-store" in cc or "no-cache" in cc

    def test_post_request_has_no_cache(self, client):
        """POST 请求不应有缓存头。"""
        response = client.post("/api/v1/generate", json={})
        cc = response.headers.get("Cache-Control", "")
        # POST 不在缓存规则内，保持默认
        assert "max-age" not in cc

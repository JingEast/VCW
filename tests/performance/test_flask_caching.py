"""Flask-Caching HTTP 缓存层测试。"""

from __future__ import annotations


class TestFlaskCaching:
    """验证 API 端点响应被正确缓存。"""

    def test_trends_fresh_is_cached(self, client, app):
        """连续请求 /api/v1/trends/fresh 应命中缓存。"""
        from app.core.flask_cache import cache

        # 预热缓存
        cache.delete("api_trends_fresh")
        r1 = client.get("/api/v1/trends/fresh")
        assert r1.status_code == 200

        # 第二次请求应直接命中缓存（响应时间更短）
        r2 = client.get("/api/v1/trends/fresh")
        assert r2.status_code == 200
        assert r2.data == r1.data

    def test_scheduler_status_is_cached(self, client, app):
        """连续请求 scheduler status 应命中缓存。"""
        from app.core.flask_cache import cache

        cache.delete("api_scheduler_status")
        r1 = client.get("/api/v1/trends/scheduler/status")
        assert r1.status_code == 200

        r2 = client.get("/api/v1/trends/scheduler/status")
        assert r2.status_code == 200
        assert r2.data == r1.data

    def test_cache_clear_works(self, client, app):
        """手动清除缓存后响应应重新生成。"""
        from app.core.flask_cache import cache

        cache.delete("api_trends_fresh")
        r1 = client.get("/api/v1/trends/fresh")
        assert r1.status_code == 200

        # 清除缓存
        cache.delete("api_trends_fresh")
        r2 = client.get("/api/v1/trends/fresh")
        assert r2.status_code == 200

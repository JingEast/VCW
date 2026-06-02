"""LocalTTLCache 与 @cached 装饰器测试。"""

from __future__ import annotations

import time


class TestLocalTTLCache:
    """验证内存 TTL 缓存核心行为。"""

    def test_basic_get_set(self):
        from app.core.cache import LocalTTLCache

        cache = LocalTTLCache(ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_ttl_expiration(self):
        from app.core.cache import LocalTTLCache

        cache = LocalTTLCache(ttl=0.05)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(0.1)
        try:
            cache.get("key")
            raise AssertionError("expected KeyError")
        except KeyError:
            pass

    def test_maxsize_eviction(self):
        from app.core.cache import LocalTTLCache

        cache = LocalTTLCache(ttl=60, maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.get("d") == 4
        # a 应该被淘汰（最早过期策略）
        try:
            cache.get("a")
            raise AssertionError("expected KeyError")
        except KeyError:
            pass

    def test_clear(self):
        from app.core.cache import LocalTTLCache

        cache = LocalTTLCache(ttl=60)
        cache.set("key", "value")
        cache.clear()
        try:
            cache.get("key")
            raise AssertionError("expected KeyError")
        except KeyError:
            pass


class TestCachedDecorator:
    """验证 @cached 装饰器行为。"""

    def test_caches_function_result(self):
        from app.core.cache import cached

        call_count = 0

        @cached(ttl_seconds=60)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(5) == 10
        assert compute(5) == 10
        assert call_count == 1  # 第二次命中缓存

    def test_different_args_different_cache(self):
        from app.core.cache import cached

        call_count = 0

        @cached(ttl_seconds=60)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        compute(6)
        assert call_count == 2

    def test_cache_clear(self):
        from app.core.cache import cached

        call_count = 0

        @cached(ttl_seconds=60)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        compute.cache_clear()  # type: ignore[attr-defined]
        compute(5)
        assert call_count == 2

    def test_ttl_expires(self):
        from app.core.cache import cached

        call_count = 0

        @cached(ttl_seconds=0.05)
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        compute(5)
        time.sleep(0.1)
        compute(5)
        assert call_count == 2


class TestRepositoryCacheIntegration:
    """验证 Repository 层缓存与清除的端到端行为。"""

    def test_trend_get_all_cached(self, app):
        from vcw_copywriter.db.repositories.trend_repository import TrendRepository
        from vcw_copywriter.db.session import get_session

        session = get_session()
        repo = TrendRepository(session)
        repo.add(title="cache-test-1", category="测试")
        result1 = repo.get_all(limit=10)
        result2 = repo.get_all(limit=10)
        assert result1 == result2
        # 写操作后缓存应被清除
        repo.add(title="cache-test-2", category="测试")
        result3 = repo.get_all(limit=10)
        assert result3[1] > result1[1] or result3[0][0].title != result1[0][0].title
        session.close()

    def test_memory_count_pending_cached(self, app):
        from vcw_copywriter.db.repositories.memory_repository import MemoryRepository
        from vcw_copywriter.db.session import get_session

        session = get_session()
        repo = MemoryRepository(session)
        repo.add_entry(topic="cache-topic", issue_description="desc", issue_tags=["a"], correction_plan="fix it")
        c1 = repo.count_pending()
        c2 = repo.count_pending()
        assert c1 == c2
        repo.mark_avoided(repo.get_recent_entries(1)[0].id)
        c3 = repo.count_pending()
        assert c3 < c1
        session.close()

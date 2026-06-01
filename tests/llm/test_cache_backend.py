"""测试 LLM Cache 后端实现。"""

from __future__ import annotations

import time

import pytest

from llm.adapter.base import LLMResponse, TokenUsage
from llm.cache.base import BaseCacheBackend, CacheEntry
from llm.cache.memory_backend import MemoryCacheBackend


class TestCacheEntry:
    """验证 CacheEntry 数据类行为。"""

    def test_cache_entry_immutable(self):
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=60,
        )
        with pytest.raises(AttributeError):
            entry.ttl_seconds = 30


class TestMemoryCacheBackend:
    """验证 MemoryCacheBackend 完整行为。"""

    def test_get_missing_key_returns_none(self):
        cache = MemoryCacheBackend()
        assert cache.get("missing") is None

    def test_set_and_get_round_trip(self):
        cache = MemoryCacheBackend()
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=60,
        )
        cache.set("key1", entry)
        retrieved = cache.get("key1")
        assert retrieved is not None
        assert retrieved.response.content == "hello"
        assert retrieved.ttl_seconds == 60

    def test_expired_entry_returns_none_and_removes(self):
        cache = MemoryCacheBackend()
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=0,
        )
        cache.set("expired", entry)
        time.sleep(0.01)
        assert cache.get("expired") is None
        assert "expired" not in cache._store

    def test_delete_existing_key(self):
        cache = MemoryCacheBackend()
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=60,
        )
        cache.set("del-key", entry)
        assert cache.delete("del-key") is True
        assert cache.get("del-key") is None

    def test_delete_missing_key_returns_false(self):
        cache = MemoryCacheBackend()
        assert cache.delete("missing") is False

    def test_clear_removes_all(self):
        cache = MemoryCacheBackend()
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=60,
        )
        cache.set("a", entry)
        cache.set("b", entry)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert len(cache._store) == 0

    def test_lru_eviction_on_max_size(self):
        cache = MemoryCacheBackend(max_size=2)
        entry = CacheEntry(
            response=LLMResponse(
                content="hello",
                provider="openai",
                model="gpt-4o",
                usage=TokenUsage(),
                latency_ms=0.0,
            ),
            ttl_seconds=60,
        )
        cache.set("a", entry)
        cache.set("b", entry)
        cache.set("c", entry)
        # 最早插入的 a 应该被驱逐
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None


class TestBaseCacheBackendMakeKey:
    """验证 BaseCacheBackend.make_key 哈希行为。"""

    def test_same_input_same_key(self):
        class DummyBackend(BaseCacheBackend):
            def get(self, key):
                pass

            def set(self, key, entry):
                pass

            def delete(self, key):
                pass

            def clear(self):
                pass

        backend = DummyBackend()
        key1 = backend.make_key([{"role": "user", "content": "hi"}], "openai")
        key2 = backend.make_key([{"role": "user", "content": "hi"}], "openai")
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex

    def test_different_input_different_key(self):
        class DummyBackend(BaseCacheBackend):
            def get(self, key):
                pass

            def set(self, key, entry):
                pass

            def delete(self, key):
                pass

            def clear(self):
                pass

        backend = DummyBackend()
        key1 = backend.make_key([{"role": "user", "content": "hi"}], "openai")
        key2 = backend.make_key([{"role": "user", "content": "hello"}], "openai")
        assert key1 != key2

    def test_kwargs_affect_key(self):
        class DummyBackend(BaseCacheBackend):
            def get(self, key):
                pass

            def set(self, key, entry):
                pass

            def delete(self, key):
                pass

            def clear(self):
                pass

        backend = DummyBackend()
        key1 = backend.make_key([{"role": "user", "content": "hi"}], "openai")
        key2 = backend.make_key([{"role": "user", "content": "hi"}], "openai", temperature=0.5)
        assert key1 != key2

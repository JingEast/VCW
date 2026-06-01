"""Async & Concurrency Edge Case Tests

验证线程安全、资源泄漏与并发边界行为。
"""

import threading

from llm.cache.memory_backend import MemoryCacheBackend
from llm.fallback.chain_strategy import ChainFallbackStrategy
from llm.tracing.otel_tracing import OtelTracingMiddleware
from llm.adapter.base import LLMResponse, TokenUsage


class TestMemoryCacheThreadSafety:
    """内存缓存线程安全测试"""

    def test_concurrent_set_no_crash(self):
        cache = MemoryCacheBackend(max_size=100)
        errors = []

        def worker(i):
            try:
                for j in range(50):
                    cache.set(f"key-{i}-{j}", type("CacheEntry", (), {"ttl_seconds": 60})())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent set raised: {errors}"
        assert len(cache._store) <= 100

    def test_concurrent_get_set_delete(self):
        cache = MemoryCacheBackend(max_size=50)
        errors = []

        def setter():
            for i in range(200):
                try:
                    cache.set(f"k{i}", type("CacheEntry", (), {"ttl_seconds": 60})())
                except Exception as exc:
                    errors.append(exc)

        def getter():
            for i in range(200):
                try:
                    cache.get(f"k{i}")
                except Exception as exc:
                    errors.append(exc)

        def deleter():
            for i in range(200):
                try:
                    cache.delete(f"k{i}")
                except Exception as exc:
                    errors.append(exc)

        threads = (
            [threading.Thread(target=setter) for _ in range(3)]
            + [threading.Thread(target=getter) for _ in range(3)]
            + [threading.Thread(target=deleter) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent operations raised: {errors}"


class TestFallbackHistoryThreadSafety:
    """Fallback 策略线程安全测试"""

    def test_concurrent_record_result(self):
        strategy = ChainFallbackStrategy(priority=["a", "b", "c"])
        errors = []

        def worker(i):
            try:
                for _ in range(100):
                    strategy.record_result("a", True, 10.0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        with strategy._lock:
            assert len(strategy._history["a"]) == 1000


class TestTracingSpanCleanup:
    """Tracing span 泄漏测试"""

    def test_spans_cleaned_up_after_post_call(self):
        tracer = OtelTracingMiddleware()

        for i in range(100):
            ctx = tracer.pre_call(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                trace_id=f"trace-{i}",
            )
            tracer.post_call(
                ctx,
                response=LLMResponse(
                    content="hello",
                    provider="openai",
                    model="gpt-4o",
                    usage=TokenUsage(1, 1, 2),
                    latency_ms=10.0,
                ),
            )

        with tracer._lock:
            assert len(tracer._spans) == 0, "Spans leaked after post_call"

    def test_spans_cleaned_up_on_exception(self):
        tracer = OtelTracingMiddleware()

        for i in range(100):
            ctx = tracer.pre_call(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                trace_id=f"trace-{i}",
            )
            tracer.post_call(ctx, error=RuntimeError("boom"))

        with tracer._lock:
            assert len(tracer._spans) == 0, "Spans leaked on error path"

    def test_concurrent_pre_post_call_no_crash(self):
        tracer = OtelTracingMiddleware()
        errors = []

        def worker(i):
            try:
                for j in range(50):
                    ctx = tracer.pre_call(
                        messages=[{"role": "user", "content": "hi"}],
                        provider="openai",
                        trace_id=f"trace-{i}-{j}",
                    )
                    tracer.post_call(
                        ctx,
                        response=LLMResponse(
                            content="hello",
                            provider="openai",
                            model="gpt-4o",
                            usage=TokenUsage(1, 1, 2),
                            latency_ms=10.0,
                        ),
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        with tracer._lock:
            assert len(tracer._spans) == 0


class TestAdapterClose:
    """Adapter 资源关闭测试"""

    def test_openai_adapter_close(self):
        from llm.adapter.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(api_key="test", model="gpt-4o")
        adapter.close()

    def test_anthropic_adapter_close(self):
        from llm.adapter.anthropic_adapter import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test", model="claude-3")
        adapter.close()

    def test_gemini_adapter_close(self):
        from llm.adapter.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(api_key="test", model="gemini-pro")
        adapter.close()

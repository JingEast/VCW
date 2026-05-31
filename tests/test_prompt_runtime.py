"""Prompt Runtime 单元测试"""

import json
import tempfile
from unittest.mock import MagicMock

import pytest

from prompt_runtime import (
    CacheEntry,
    DegradeContent,
    FallbackExhaustedError,
    HashKeyStrategy,
    IPromptCache,
    ModelFallbackStrategy,
    PromptCache,
    PromptCallInfo,
    PromptExecutionContext,
    PromptExecutor,
    PromptMetricsCollector,
    PromptResult,
    PromptRetryPolicy,
    PromptRetryWithFallback,
    PromptTracer,
    PromptTraceMiddleware,
    PromptTraceRecord,
    PromptTraceRequest,
    PromptTraceResponse,
    RedisPromptCache,
    RetryConfig,
)


class TestPromptTraceRecord:
    """PromptTraceRecord 序列化测试"""

    def test_to_dict_structure(self):
        record = PromptTraceRecord(
            trace_id="abc123",
            timestamp="2026-05-31T12:00:00",
            request=PromptTraceRequest(
                system_prompt="sys",
                user_prompt="user",
                model="gpt-4",
                temperature=0.5,
                max_tokens=100,
            ),
            response=PromptTraceResponse(
                success=True,
                content="hello",
                meta="meta-info",
                token_usage={"prompt_tokens": 10, "completion_tokens": 5},
            ),
            latency_ms=123.4,
            model="gpt-4",
        )
        d = record.to_dict()
        assert d["trace_id"] == "abc123"
        assert d["request"]["user_prompt"] == "user"
        assert d["response"]["token_usage"]["completion_tokens"] == 5
        assert d["latency_ms"] == 123.4

    def test_to_json_roundtrip(self):
        record = PromptTraceRecord(
            trace_id="abc123",
            timestamp="2026-05-31T12:00:00",
            request=PromptTraceRequest(system_prompt="s", user_prompt="u"),
            response=PromptTraceResponse(success=True, content="c"),
            latency_ms=10.0,
        )
        s = record.to_json()
        loaded = json.loads(s)
        assert loaded["trace_id"] == "abc123"
        assert loaded["request"]["system_prompt"] == "s"


class TestPromptTracer:
    """PromptTracer 功能测试"""

    def test_generate_trace_id_is_hex(self):
        tracer = PromptTracer()
        tid = tracer.generate_trace_id()
        assert isinstance(tid, str)
        assert len(tid) == 32
        assert int(tid, 16) >= 0

    def test_trace_and_get_trace(self):
        tracer = PromptTracer()
        record = PromptTraceRecord(
            trace_id="tid-001",
            timestamp="2026-05-31T12:00:00",
            request=PromptTraceRequest(),
            response=PromptTraceResponse(),
            latency_ms=0.0,
        )
        tracer.trace(record)
        found = tracer.get_trace("tid-001")
        assert found is not None
        assert found.trace_id == "tid-001"

    def test_get_trace_not_found_returns_none(self):
        tracer = PromptTracer()
        assert tracer.get_trace("nonexistent") is None

    def test_list_traces_pagination(self):
        tracer = PromptTracer()
        for i in range(5):
            tracer.trace(
                PromptTraceRecord(
                    trace_id=f"tid-{i}",
                    timestamp="2026-05-31T12:00:00",
                    request=PromptTraceRequest(),
                    response=PromptTraceResponse(),
                    latency_ms=0.0,
                )
            )
        assert len(tracer.list_traces(limit=2, offset=0)) == 2
        assert len(tracer.list_traces(limit=10, offset=0)) == 5

    def test_max_records_eviction(self):
        tracer = PromptTracer(max_records=3)
        for i in range(5):
            tracer.trace(
                PromptTraceRecord(
                    trace_id=f"tid-{i}",
                    timestamp="2026-05-31T12:00:00",
                    request=PromptTraceRequest(),
                    response=PromptTraceResponse(),
                    latency_ms=0.0,
                )
            )
        assert len(tracer._records) == 3
        assert tracer.get_trace("tid-0") is None
        assert tracer.get_trace("tid-4") is not None

    def test_export_json_logs(self):
        tracer = PromptTracer()
        tracer.trace(
            PromptTraceRecord(
                trace_id="tid-001",
                timestamp="2026-05-31T12:00:00",
                request=PromptTraceRequest(system_prompt="sys"),
                response=PromptTraceResponse(success=True, content="ok"),
                latency_ms=100.0,
            )
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        tracer.export_json_logs(path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        loaded = json.loads(lines[0])
        assert loaded["trace_id"] == "tid-001"


class TestPromptTraceMiddleware:
    """PromptTraceMiddleware 自动追踪测试"""

    def test_execute_records_success(self):
        mock_executor = MagicMock(spec=PromptExecutor)
        mock_executor.execute.return_value = PromptResult(
            success=True,
            content="生成的文案",
            meta="mock-meta",
            token_usage={"total_tokens": 150},
        )
        tracer = PromptTracer()
        middleware = PromptTraceMiddleware(mock_executor, tracer)

        ctx = PromptExecutionContext(
            system_prompt="sys",
            user_prompt="user",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
        )
        result = middleware.execute(ctx)

        assert result.success is True
        assert result.content == "生成的文案"
        assert len(tracer._records) == 1
        record = tracer._records[0]
        assert record.request.system_prompt == "sys"
        assert record.response.content == "生成的文案"
        assert record.response.token_usage == {"total_tokens": 150}
        assert record.latency_ms >= 0
        assert record.error is None

    def test_execute_records_error(self):
        mock_executor = MagicMock(spec=PromptExecutor)
        mock_executor.execute.side_effect = RuntimeError("LLM timeout")
        tracer = PromptTracer()
        middleware = PromptTraceMiddleware(mock_executor, tracer)

        ctx = PromptExecutionContext(user_prompt="user", model="gpt-4")
        with pytest.raises(RuntimeError, match="LLM timeout"):
            middleware.execute(ctx)

        assert len(tracer._records) == 1
        record = tracer._records[0]
        assert record.error == "LLM timeout"
        assert record.response.success is False

    def test_execute_stream_records_success(self):
        mock_executor = MagicMock(spec=PromptExecutor)

        def fake_stream(ctx):
            yield type("Chunk", (), {"text": "第1段", "is_done": False, "is_error": False, "meta": ""})()
            yield type("Chunk", (), {"text": "第2段", "is_done": False, "is_error": False, "meta": ""})()
            yield type("Chunk", (), {"text": "done", "is_done": True, "is_error": False, "meta": "meta-info"})()

        mock_executor.execute_stream = fake_stream
        tracer = PromptTracer()
        middleware = PromptTraceMiddleware(mock_executor, tracer)

        ctx = PromptExecutionContext(user_prompt="user", model="gpt-4")
        chunks = list(middleware.execute_stream(ctx))

        assert len(chunks) == 3
        assert len(tracer._records) == 1
        record = tracer._records[0]
        assert record.response.content == "第1段第2段"
        assert record.response.meta == "meta-info"
        assert record.latency_ms >= 0

    def test_execute_stream_records_error(self):
        mock_executor = MagicMock(spec=PromptExecutor)

        def fake_stream(ctx):
            yield type("Chunk", (), {"text": "err", "is_done": False, "is_error": True, "meta": ""})()

        mock_executor.execute_stream = fake_stream
        tracer = PromptTracer()
        middleware = PromptTraceMiddleware(mock_executor, tracer)

        ctx = PromptExecutionContext(user_prompt="user", model="gpt-4")
        chunks = list(middleware.execute_stream(ctx))

        assert len(chunks) == 1
        record = tracer._records[0]
        assert record.error == "err"


class TestPromptMetricsCollector:
    """PromptMetricsCollector 指标测试"""

    def test_empty_snapshot(self):
        collector = PromptMetricsCollector(enable_prometheus=False)
        m = collector.get_snapshot()
        assert m.total_calls == 0
        assert m.avg_latency_ms == 0.0

    def test_record_and_aggregate(self):
        collector = PromptMetricsCollector(enable_prometheus=False)
        collector.record(PromptCallInfo(latency_ms=100.0, input_tokens=30, output_tokens=20, success=True, model="gpt-4o"))
        collector.record(PromptCallInfo(latency_ms=200.0, input_tokens=60, output_tokens=40, success=False, model="gpt-4o"))
        m = collector.get_snapshot()
        assert m.total_calls == 2
        assert m.total_input_tokens == 90
        assert m.total_output_tokens == 60
        assert m.total_tokens == 150
        assert m.avg_latency_ms == 150.0
        assert m.error_rate == 0.5
        assert m.model_distribution == {"gpt-4o": 2}
        assert m.total_cost > 0

    def test_percentiles(self):
        collector = PromptMetricsCollector(enable_prometheus=False)
        for i in range(1, 11):
            collector.record(PromptCallInfo(latency_ms=float(i * 10), input_tokens=10, output_tokens=10, success=True, model="gpt-4o"))
        m = collector.get_snapshot()
        assert m.p50_latency_ms == 55.0
        # linear interpolation: p90 = 90 * 0.9 + 100 * 0.1 = 91
        assert m.p90_latency_ms == 91.0
        assert m.p99_latency_ms == 99.1
        assert m.min_latency_ms == 10.0
        assert m.max_latency_ms == 100.0

    def test_get_by_model(self):
        collector = PromptMetricsCollector(enable_prometheus=False)
        collector.record(PromptCallInfo(latency_ms=100.0, input_tokens=10, output_tokens=10, success=True, model="gpt-4o"))
        collector.record(PromptCallInfo(latency_ms=200.0, input_tokens=20, output_tokens=20, success=True, model="moonshot-v1-8k"))
        gpt = collector.get_by_model("gpt-4o")
        assert gpt.total_calls == 1
        assert gpt.avg_latency_ms == 100.0
        moon = collector.get_by_model("moonshot-v1-8k")
        assert moon.total_calls == 1
        assert moon.avg_latency_ms == 200.0

    def test_window_filtering(self):
        import time as _time

        collector = PromptMetricsCollector(enable_prometheus=False)
        collector.record(PromptCallInfo(latency_ms=100.0, input_tokens=10, output_tokens=10, success=True, model="gpt-4o", timestamp=_time.time() - 10))
        collector.record(PromptCallInfo(latency_ms=200.0, input_tokens=10, output_tokens=10, success=True, model="gpt-4o", timestamp=_time.time()))
        m = collector.get_snapshot(window_seconds=5)
        assert m.total_calls == 1
        assert m.avg_latency_ms == 200.0

    def test_cost_computation(self):
        from prompt_runtime import compute_cost
        cost = compute_cost("gpt-4o", 1000, 1000)
        # input: 1000 * 0.005 / 1000 = 0.005, output: 1000 * 0.015 / 1000 = 0.015
        assert cost == 0.02

    def test_reset(self):
        collector = PromptMetricsCollector(enable_prometheus=False)
        collector.record(PromptCallInfo(latency_ms=100.0, input_tokens=10, output_tokens=10))
        collector.reset()
        m = collector.get_snapshot()
        assert m.total_calls == 0

    def test_prometheus_expose(self):
        collector = PromptMetricsCollector(enable_prometheus=True)
        data = collector.expose_prometheus()
        assert isinstance(data, bytes)
        assert b"# HELP" in data or b"Prometheus not enabled" in data


class TestPromptCache:
    """PromptCache 缓存测试"""

    def test_get_miss_returns_none(self):
        cache = PromptCache()
        assert cache.get("missing") is None

    def test_set_and_get(self):
        cache = PromptCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_invalidate(self):
        cache = PromptCache()
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = PromptCache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_ttl_expiration(self):
        cache = PromptCache()
        cache.set("key1", "value1", ttl_seconds=-1)
        assert cache.get("key1") is None


class TestHashKeyStrategy:
    """HashKeyStrategy 测试"""

    def test_same_input_same_key(self):
        strategy = HashKeyStrategy()
        k1 = strategy.generate("sys", "user", "gpt-4", 0.7, 2000)
        k2 = strategy.generate("sys", "user", "gpt-4", 0.7, 2000)
        assert k1 == k2
        assert len(k1) == 64  # sha256 hex

    def test_different_input_different_key(self):
        strategy = HashKeyStrategy()
        k1 = strategy.generate("sys1", "user", "gpt-4", 0.7, 2000)
        k2 = strategy.generate("sys2", "user", "gpt-4", 0.7, 2000)
        assert k1 != k2

    def test_extra_influences_key(self):
        strategy = HashKeyStrategy()
        k1 = strategy.generate("sys", "user", "gpt-4", 0.7, 2000, extra={"topic": "A"})
        k2 = strategy.generate("sys", "user", "gpt-4", 0.7, 2000, extra={"topic": "B"})
        assert k1 != k2


class TestRedisPromptCache:
    """RedisPromptCache 测试（mock Redis）"""

    def test_redis_get_set(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        cache = RedisPromptCache(redis_client=mock_redis)
        assert cache.get("key1") is None
        cache.set("key1", "value1", ttl_seconds=60)
        mock_redis.setex.assert_called_once()

    def test_redis_fallback_on_failure(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("Redis down")
        fallback = PromptCache()
        fallback.set("key1", "fallback_value")
        cache = RedisPromptCache(redis_client=mock_redis, fallback_store=fallback)
        assert cache.get("key1") == "fallback_value"

    def test_redis_without_client_uses_fallback(self):
        fallback = PromptCache()
        cache = RedisPromptCache(redis_client=None, fallback_store=fallback)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"


class TestModelFallbackStrategy:
    """ModelFallbackStrategy 测试"""

    def test_primary_success(self):
        strategy = ModelFallbackStrategy()
        success, result = strategy.execute(
            primary_fn=lambda: "primary_result",
            fallback_chain=[],
        )
        assert success is True
        assert result == "primary_result"

    def test_fallback_on_primary_failure(self):
        strategy = ModelFallbackStrategy()
        success, result = strategy.execute(
            primary_fn=lambda: (_ for _ in ()).throw(RuntimeError("primary fail")),
            fallback_chain=[lambda: "fallback_result"],
        )
        assert success is True
        assert result == "fallback_result"

    def test_degrade_when_all_fail(self):
        strategy = ModelFallbackStrategy()
        degrade = DegradeContent(content="degraded_content")
        success, result = strategy.execute(
            primary_fn=lambda: (_ for _ in ()).throw(RuntimeError("fail")),
            fallback_chain=[lambda: (_ for _ in ()).throw(RuntimeError("fail2"))],
            degrade_content=degrade,
        )
        assert success is True
        assert result == degrade

    def test_exhausted_error_without_degrade(self):
        strategy = ModelFallbackStrategy()
        with pytest.raises(FallbackExhaustedError):
            strategy.execute(
                primary_fn=lambda: (_ for _ in ()).throw(RuntimeError("fail")),
                fallback_chain=[lambda: (_ for _ in ()).throw(RuntimeError("fail2"))],
            )


class TestPromptRetryPolicy:
    """PromptRetryPolicy 测试"""

    def test_success_no_retry(self):
        policy = PromptRetryPolicy(RetryConfig(max_retries=2))
        result = policy.execute(lambda: "ok")
        assert result == "ok"

    def test_retry_on_retryable_error_then_success(self):
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise TimeoutError("timeout")
            return "ok"

        policy = PromptRetryPolicy(
            RetryConfig(max_retries=3, base_delay_ms=10, jitter=False)
        )
        result = policy.execute(flaky)
        assert result == "ok"
        assert call_count[0] == 3

    def test_no_retry_on_non_retryable_error(self):
        call_count = [0]

        def bad():
            call_count[0] += 1
            raise ValueError("bad arg")

        policy = PromptRetryPolicy(
            RetryConfig(max_retries=3, base_delay_ms=10, jitter=False)
        )
        with pytest.raises(ValueError):
            policy.execute(bad)
        assert call_count[0] == 1

    def test_max_retries_exhausted(self):
        call_count = [0]

        def always_fail():
            call_count[0] += 1
            raise TimeoutError("timeout")

        policy = PromptRetryPolicy(
            RetryConfig(max_retries=2, base_delay_ms=10, jitter=False)
        )
        with pytest.raises(TimeoutError):
            policy.execute(always_fail)
        assert call_count[0] == 3  # initial + 2 retries


class TestPromptRetryWithFallback:
    """PromptRetryWithFallback 组合策略测试"""

    def test_retry_then_fallback(self):
        call_counts = {"primary": 0, "fallback": 0}

        def primary():
            call_counts["primary"] += 1
            raise TimeoutError("timeout")

        def fallback():
            call_counts["fallback"] += 1
            return "fallback_ok"

        retry = PromptRetryWithFallback(
            retry_config=RetryConfig(max_retries=1, base_delay_ms=10, jitter=False),
            fallback_strategy=ModelFallbackStrategy(),
        )
        success, result = retry.execute_with_fallback(primary, [fallback])
        assert success is True
        assert result == "fallback_ok"
        assert call_counts["primary"] == 2  # initial + 1 retry
        assert call_counts["fallback"] == 1  # fallback succeeds on first try

    def test_all_exhausted_with_degrade(self):
        def primary():
            raise TimeoutError("timeout")

        def fallback():
            raise TimeoutError("timeout")

        retry = PromptRetryWithFallback(
            retry_config=RetryConfig(max_retries=0, base_delay_ms=10, jitter=False),
            fallback_strategy=ModelFallbackStrategy(),
        )
        success, result = retry.execute_with_fallback(primary, [fallback])
        assert success is True
        assert isinstance(result, DegradeContent)
        assert result.success is False

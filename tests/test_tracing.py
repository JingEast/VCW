"""OpenTelemetry Tracing 测试。

验证：
  1. OtelTracingMiddleware pre_call / post_call 创建/结束 span
  2. GatewayTracer model_call_span / retry_span / fallback_span
  3. retry.py 的 before_sleep 回调注入 retry event
  4. fallback chain strategy 注入 fallback event
  5. exporter config 环境变量解析
  6. 未安装 opentelemetry 时自动降级为 no-op
  7. gateway/core.py 中 model call span 包装
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from llm.adapter.base import LLMResponse, TokenUsage
from llm.adapter.retry import RETRYABLE_EXCEPTIONS, with_llm_retry
from llm.adapter.exceptions import LLMRateLimitError, LLMServiceUnavailableError
from llm.fallback.chain_strategy import ChainFallbackStrategy
from llm.gateway.config import GatewayConfig
from llm.gateway.core import LLMGateway
from llm.gateway.registry import ProviderRegistry
from llm.tracing import (
    GatewayTracer,
    LogTracingMiddleware,
    OtelTracingMiddleware,
    TracingExporterConfig,
)
from llm.tracing.base import TraceContext


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.provider_name = "openai"
    adapter.model = "gpt-4o"
    adapter.chat.return_value = LLMResponse(
        content="Hello!",
        provider="openai",
        model="gpt-4o",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=123.0,
    )
    adapter.embed.return_value = [[0.1, 0.2]]
    adapter.health_check.return_value = MagicMock(value="healthy")
    return adapter


@pytest.fixture
def mock_otel_span():
    """返回一个模拟的 OpenTelemetry Span。"""
    span = MagicMock()
    span.is_recording.return_value = True
    span.get_span_context.return_value = MagicMock(span_id="abc123")
    return span


@pytest.fixture
def mock_otel_tracer(mock_otel_span):
    """返回一个模拟的 OpenTelemetry Tracer。"""
    tracer = MagicMock()
    tracer.start_span.return_value = mock_otel_span
    tracer.start_as_current_span.return_value.__enter__ = lambda *a: mock_otel_span
    tracer.start_as_current_span.return_value.__exit__ = lambda *a: None
    return tracer


# =============================================================================
# OtelTracingMiddleware Tests
# =============================================================================


class TestOtelTracingMiddleware:
    """OpenTelemetry Tracing Middleware 测试。"""

    def test_pre_call_creates_span(self, mock_otel_tracer, mock_otel_span):
        """pre_call 创建 span 并设置 attributes。"""
        middleware = OtelTracingMiddleware(tracer=mock_otel_tracer)
        ctx = middleware.pre_call(
            [{"role": "user", "content": "hi"}],
            "openai",
            user="alice",
            model="gpt-4o",
            temperature=0.7,
        )

        assert isinstance(ctx, TraceContext)
        mock_otel_tracer.start_span.assert_called_once()
        call_kwargs = mock_otel_tracer.start_span.call_args[1]
        assert call_kwargs["attributes"]["llm.provider"] == "openai"
        assert call_kwargs["attributes"]["llm.user"] == "alice"
        assert call_kwargs["attributes"]["llm.messages.count"] == 1
        mock_otel_span.set_attribute.assert_any_call("llm.temperature", 0.7)

    def test_post_call_ends_span_with_ok(self, mock_otel_tracer, mock_otel_span):
        """post_call 正常结束时设置 OK 并结束 span。"""
        middleware = OtelTracingMiddleware(tracer=mock_otel_tracer)
        ctx = middleware.pre_call([{"role": "user", "content": "hi"}], "openai")

        response = LLMResponse(
            content="OK",
            provider="openai",
            model="gpt-4o",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            latency_ms=100.0,
        )
        middleware.post_call(ctx, response=response)

        mock_otel_span.set_attribute.assert_any_call("llm.response.tokens.prompt", 5)
        mock_otel_span.set_attribute.assert_any_call("llm.response.tokens.completion", 3)
        mock_otel_span.end.assert_called_once()

    def test_post_call_ends_span_with_error(self, mock_otel_tracer, mock_otel_span):
        """post_call 异常结束时设置 ERROR 并记录 exception。"""
        middleware = OtelTracingMiddleware(tracer=mock_otel_tracer)
        ctx = middleware.pre_call([{"role": "user", "content": "hi"}], "openai")

        error = RuntimeError("boom")
        middleware.post_call(ctx, error=error)

        mock_otel_span.record_exception.assert_called_once_with(error)
        mock_otel_span.end.assert_called_once()

    def test_post_call_without_pre_call_no_crash(self):
        """post_call 在没有对应 pre_call 时不崩溃。"""
        middleware = OtelTracingMiddleware()
        ctx = TraceContext(trace_id="missing", span_id="x")
        middleware.post_call(ctx)  # 不应抛异常

    def test_start_child_span(self, mock_otel_tracer, mock_otel_span):
        """start_child_span 从 parent span 启动子 span。"""
        middleware = OtelTracingMiddleware(tracer=mock_otel_tracer)
        parent_ctx = middleware.pre_call([{"role": "user", "content": "hi"}], "openai")

        child = middleware.start_child_span("llm.model.call", parent_ctx, {"key": "val"})
        assert child is mock_otel_span
        mock_otel_tracer.start_span.assert_called()


# =============================================================================
# GatewayTracer Tests
# =============================================================================


class TestGatewayTracer:
    """GatewayTracer 子 span 助手测试。"""

    def test_model_call_span(self, mock_otel_tracer, mock_otel_span):
        """model_call_span 创建正确 attributes 的 span。"""
        with patch("llm.tracing.otel_tracing._get_tracer", return_value=mock_otel_tracer):
            with GatewayTracer.model_call_span("openai", "gpt-4o") as span:
                assert span is mock_otel_span
        call_kwargs = mock_otel_tracer.start_as_current_span.call_args[1]
        assert call_kwargs["attributes"]["llm.provider"] == "openai"
        assert call_kwargs["attributes"]["llm.model"] == "gpt-4o"

    def test_retry_span(self, mock_otel_tracer, mock_otel_span):
        """retry_span 创建 retry 信息 span。"""
        with patch("llm.tracing.otel_tracing._get_tracer", return_value=mock_otel_tracer):
            GatewayTracer.retry_span(attempt=2, max_attempts=3, exception=LLMRateLimitError("rate"))
        call_kwargs = mock_otel_tracer.start_span.call_args[1]
        assert call_kwargs["attributes"]["retry.attempt"] == 2
        assert call_kwargs["attributes"]["retry.max_attempts"] == 3
        mock_otel_span.set_attribute.assert_called_once_with("retry.exception", "LLMRateLimitError")
        mock_otel_span.record_exception.assert_called_once()
        mock_otel_span.end.assert_called_once()

    def test_fallback_span(self, mock_otel_tracer, mock_otel_span):
        """fallback_span 创建 fallback 信息 span。"""
        with patch("llm.tracing.otel_tracing._get_tracer", return_value=mock_otel_tracer):
            GatewayTracer.fallback_span("openai", "anthropic", "rate limit")
        call_kwargs = mock_otel_tracer.start_span.call_args[1]
        assert call_kwargs["attributes"]["fallback.from_provider"] == "openai"
        assert call_kwargs["attributes"]["fallback.to_provider"] == "anthropic"
        assert call_kwargs["attributes"]["fallback.reason"] == "rate limit"
        mock_otel_span.end.assert_called_once()


# =============================================================================
# Retry Tracing Tests
# =============================================================================


class TestRetryTracing:
    """Retry 阶段 tracing 测试。"""

    def test_retry_event_injected(self, mock_otel_span):
        """重试时当前 span 收到 retry event。"""
        call_count = 0

        @with_llm_retry(max_retries=3, backoff_initial=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMRateLimitError("rate limited")
            return "ok"

        # 构造假的 opentelemetry 模块让 retry.py 能 import
        fake_otel = MagicMock()
        fake_otel.trace.get_current_span.return_value = mock_otel_span
        with patch.dict("sys.modules", {"opentelemetry": fake_otel, "opentelemetry.trace": fake_otel.trace}):
            result = flaky()
            assert result == "ok"

        # 验证 add_event 被调用（before_sleep 回调）
        assert mock_otel_span.add_event.call_count >= 2  # 至少 2 次重试事件

    def test_retry_without_otel_does_not_crash(self):
        """未安装 opentelemetry 时重试不崩溃。"""
        call_count = 0

        @with_llm_retry(max_retries=2, backoff_initial=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMServiceUnavailableError("down")
            return "ok"

        with patch.dict("sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}):
            result = flaky()
            assert result == "ok"


# =============================================================================
# Fallback Tracing Tests
# =============================================================================


class TestFallbackTracing:
    """Fallback 阶段 tracing 测试。"""

    def test_fallback_event_injected(self, mock_otel_span):
        """fallback 决策时当前 span 收到 fallback event。"""
        strategy = ChainFallbackStrategy(priority=["openai", "anthropic", "gemini"])
        registry = ProviderRegistry()
        registry.register("anthropic", MagicMock())
        registry.register("gemini", MagicMock())

        fake_otel = MagicMock()
        fake_otel.trace.get_current_span.return_value = mock_otel_span
        with patch.dict("sys.modules", {"opentelemetry": fake_otel, "opentelemetry.trace": fake_otel.trace}):
            result = strategy.decide("openai", registry.list(), error=RuntimeError("boom"))

        assert result is not None
        assert result.provider == "anthropic"
        mock_otel_span.add_event.assert_called()
        call_args = mock_otel_span.add_event.call_args
        assert call_args[0][0] == "llm.fallback"
        attrs = call_args[0][1]
        assert attrs["fallback.from_provider"] == "openai"
        assert attrs["fallback.to_provider"] == "anthropic"

    def test_fallback_exhausted_event(self, mock_otel_span):
        """fallback 耗尽时记录 exhausted event。"""
        strategy = ChainFallbackStrategy(priority=["openai"])
        registry = ProviderRegistry()

        fake_otel = MagicMock()
        fake_otel.trace.get_current_span.return_value = mock_otel_span
        with patch.dict("sys.modules", {"opentelemetry": fake_otel, "opentelemetry.trace": fake_otel.trace}):
            result = strategy.decide("openai", registry.list())

        assert result is None
        mock_otel_span.add_event.assert_called()
        call_args = mock_otel_span.add_event.call_args
        attrs = call_args[0][1]
        assert attrs["fallback.result"] == "exhausted"


# =============================================================================
# Exporter Config Tests
# =============================================================================


class TestTracingExporterConfig:
    """Tracing Exporter 配置测试。"""

    def test_default_values(self):
        """默认值正确。"""
        config = TracingExporterConfig()
        assert config.service_name == "vcw-llm-gateway"
        assert config.exporter_type == "console"
        assert config.endpoint is None
        assert config.insecure is True
        assert config.timeout == 10

    def test_from_env(self):
        """环境变量解析正确。"""
        env = {
            "OTEL_SERVICE_NAME": "my-service",
            "OTEL_TRACING_EXPORTER": "otlp_http",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://jaeger:4318",
            "OTEL_EXPORTER_OTLP_INSECURE": "false",
            "OTEL_EXPORTER_OTLP_TIMEOUT": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            config = TracingExporterConfig.from_env()
        assert config.service_name == "my-service"
        assert config.exporter_type == "otlp_http"
        assert config.endpoint == "http://jaeger:4318"
        assert config.insecure is False
        assert config.timeout == 30

    def test_setup_without_opentelemetry_returns_none(self):
        """未安装 opentelemetry 时 setup_tracer_provider 返回 None。"""
        config = TracingExporterConfig()
        with patch.dict("sys.modules", {"opentelemetry": None}):
            result = config.setup_tracer_provider()
        assert result is None

    def test_create_exporter_console(self):
        """console exporter 创建成功。"""
        config = TracingExporterConfig(exporter_type="console")
        fake_exporter_mod = MagicMock()
        fake_exporter_mod.ConsoleSpanExporter = MagicMock()
        with patch.dict("sys.modules", {"opentelemetry.sdk.trace.export": fake_exporter_mod}):
            with patch.object(config, "_create_exporter", wraps=config._create_exporter):
                # 由于 sys.modules 已经被 patch，_create_exporter 内部的 import 会成功
                config._create_exporter()
                fake_exporter_mod.ConsoleSpanExporter.assert_called_once()

    def test_create_exporter_otlp(self):
        """otlp exporter 创建成功。"""
        config = TracingExporterConfig(exporter_type="otlp_http", endpoint="http://localhost:4318")
        fake_exporter_mod = MagicMock()
        fake_exporter_mod.OTLPSpanExporter = MagicMock()
        with patch.dict("sys.modules", {"opentelemetry.exporter.otlp.proto.http.trace_exporter": fake_exporter_mod}):
            config._create_exporter()
            fake_exporter_mod.OTLPSpanExporter.assert_called_once_with(endpoint="http://localhost:4318", timeout=10)


# =============================================================================
# Gateway Integration Tests
# =============================================================================


class TestTracingGatewayIntegration:
    """Gateway tracing 集成测试。"""

    def test_chat_with_otel_tracing(self, mock_adapter, mock_otel_tracer, mock_otel_span):
        """Gateway.chat 通过 OtelTracingMiddleware 产生 span。"""
        registry = ProviderRegistry()
        registry.register("openai", mock_adapter)
        config = GatewayConfig(default_provider="openai")
        gateway = LLMGateway(config, registry)

        tracing = OtelTracingMiddleware(tracer=mock_otel_tracer)
        gateway.attach_tracing(tracing)

        with patch("llm.tracing.otel_tracing._get_tracer", return_value=mock_otel_tracer):
            response = gateway.chat([{"role": "user", "content": "hi"}], user="alice")

        assert response.content == "Hello!"
        # pre_call 创建了一个 span，model_call_span 创建了另一个
        assert mock_otel_tracer.start_span.call_count >= 1
        assert mock_otel_tracer.start_as_current_span.call_count >= 1

    def test_chat_with_log_tracing(self, mock_adapter):
        """Gateway.chat 兼容 LogTracingMiddleware。"""
        registry = ProviderRegistry()
        registry.register("openai", mock_adapter)
        config = GatewayConfig(default_provider="openai")
        gateway = LLMGateway(config, registry)

        tracing = LogTracingMiddleware()
        gateway.attach_tracing(tracing)

        response = gateway.chat([{"role": "user", "content": "hi"}])
        assert response.content == "Hello!"

    def test_embed_with_otel_tracing(self, mock_adapter, mock_otel_tracer, mock_otel_span):
        """Gateway.embed 也产生 span（通过 tracing 不直接，但 metrics 记录）。"""
        registry = ProviderRegistry()
        registry.register("openai", mock_adapter)
        config = GatewayConfig(default_provider="openai")
        gateway = LLMGateway(config, registry)

        tracing = OtelTracingMiddleware(tracer=mock_otel_tracer)
        gateway.attach_tracing(tracing)

        response = gateway.embed(["hello"])
        assert response == [[0.1, 0.2]]


# =============================================================================
# No-op Fallback Tests
# =============================================================================


class TestNoopFallback:
    """未安装 opentelemetry 时的降级测试。"""

    def test_otel_middleware_noop(self):
        """未安装 opentelemetry 时 OtelTracingMiddleware 正常工作。"""
        with patch.dict("sys.modules", {"opentelemetry": None}):
            middleware = OtelTracingMiddleware()
            ctx = middleware.pre_call([{"role": "user", "content": "hi"}], "openai")
            assert isinstance(ctx, TraceContext)
            middleware.post_call(ctx)
            # 不应抛异常

    def test_gateway_tracer_noop(self):
        """未安装 opentelemetry 时 GatewayTracer 不崩溃。"""
        with patch.dict("sys.modules", {"opentelemetry": None}):
            span = GatewayTracer.model_call_span("openai", "gpt-4o")
            with span:
                pass
            GatewayTracer.retry_span(1, 3)
            GatewayTracer.fallback_span("a", "b", "reason")

    def test_decorators_noop(self):
        """trace_retry / trace_fallback 装饰器在未安装 opentelemetry 时可用。"""
        from llm.tracing.decorators import trace_retry, trace_fallback

        with patch.dict("sys.modules", {"opentelemetry": None}):
            @trace_retry()
            def my_func():
                return "ok"

            assert my_func() == "ok"

            @trace_fallback()
            def my_fallback():
                return None

            assert my_fallback() is None

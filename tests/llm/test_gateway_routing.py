"""测试 LLMGateway 路由与中间件编排。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm.adapter.base import LLMResponse, TokenUsage
from llm.gateway.llm_gateway import LLMGateway, ProviderRegistry, GatewayConfig


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.model = "gpt-4o"
    adapter.chat.return_value = LLMResponse(
        content="mocked content",
        provider="openai",
        model="gpt-4o",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=100.0,
    )
    return adapter


@pytest.fixture
def gateway(mock_adapter):
    registry = ProviderRegistry()
    registry.register("openai", mock_adapter)
    registry.register("kimi", mock_adapter)
    return LLMGateway(config=GatewayConfig(default_provider="openai"), registry=registry)


class TestGatewayRouting:
    """验证 Gateway 按 provider 名称路由到正确 adapter。"""

    def test_resolve_provider_explicit(self, gateway):
        assert gateway._resolve_provider("kimi") == "kimi"

    def test_resolve_provider_fallback_to_default(self, gateway):
        assert gateway._resolve_provider(None) == "openai"

    def test_resolve_provider_fallback_to_first_registered(self):
        registry = ProviderRegistry()
        registry.register("anthropic", MagicMock(model="claude"))
        gw = LLMGateway(config=GatewayConfig(), registry=registry)
        assert gw._resolve_provider(None) == "anthropic"

    def test_resolve_provider_empty_registry_raises(self):
        gw = LLMGateway(config=GatewayConfig(), registry=ProviderRegistry())
        with pytest.raises(RuntimeError, match="ProviderRegistry 为空"):
            gw._resolve_provider(None)


class TestGatewayChat:
    """验证 Gateway.chat() 编排流程。"""

    def test_chat_routes_to_adapter(self, gateway, mock_adapter):
        response = gateway.chat([{"role": "user", "content": "hi"}], provider="openai")
        mock_adapter.chat.assert_called_once()
        assert response.content == "mocked content"
        assert response.provider == "openai"

    def test_chat_passes_temperature_and_max_tokens(self, gateway, mock_adapter):
        gateway.chat(
            [{"role": "user", "content": "hi"}],
            provider="openai",
            temperature=0.5,
            max_tokens=100,
        )
        _, kwargs = mock_adapter.chat.call_args
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 100

    def test_chat_records_metrics_when_collector_attached(self, gateway, mock_adapter):
        metrics = MagicMock()
        gateway.attach_metrics(metrics)
        gateway.chat([{"role": "user", "content": "hi"}], provider="openai")
        metrics.record.assert_called_once()
        labels = metrics.record.call_args.kwargs["labels"]
        assert labels.provider == "openai"
        assert labels.status == "success"

    def test_chat_records_failure_metrics(self, gateway, mock_adapter):
        mock_adapter.chat.side_effect = RuntimeError("boom")
        metrics = MagicMock()
        gateway.attach_metrics(metrics)
        with pytest.raises(RuntimeError):
            gateway.chat([{"role": "user", "content": "hi"}], provider="openai")
        labels = metrics.record.call_args.kwargs["labels"]
        assert labels.status == "failure"


class TestGatewayComplete:
    """验证 Gateway.complete() 包装为 chat。"""

    def test_complete_builds_messages(self, gateway, mock_adapter):
        gateway.complete("prompt text", system="sys text", provider="openai")
        args, _ = mock_adapter.chat.call_args
        messages = args[0]
        assert messages[0] == {"role": "system", "content": "sys text"}
        assert messages[1] == {"role": "user", "content": "prompt text"}

    def test_complete_without_system(self, gateway, mock_adapter):
        gateway.complete("prompt text", provider="openai")
        args, _ = mock_adapter.chat.call_args
        messages = args[0]
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "prompt text"}

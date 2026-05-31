"""LLM Provider Adapter Mock Tests。

使用 unittest.mock 模拟 httpx 客户端，验证：
  1. 统一接口契约（chat/complete/embed/health_check）
  2. retry 触发（tenacity 装饰器在可重试异常下重试）
  3. timeout 参数传递
  4. 异常翻译（HTTP status → 统一异常类型）
  5. Factory 自动创建与 provider 映射
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from llm.adapter import (
    AnthropicAdapter,
    BaseLLMAdapter,
    GeminiAdapter,
    HealthStatus,
    LLMResponse,
    OpenAIAdapter,
    TokenUsage,
    create_adapter,
    list_providers,
    register_provider,
)
from llm.adapter.exceptions import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMBadRequestError,
    LLMNotImplementedError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from llm.adapter.retry import RETRYABLE_EXCEPTIONS, with_llm_retry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """返回一个 mock 的 httpx.Client 实例。"""
    client = MagicMock(spec=httpx.Client)
    # 默认 post/get 返回一个 mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    client.post.return_value = mock_response
    client.get.return_value = mock_response
    return client, mock_response


# =============================================================================
# OpenAI Adapter Tests
# =============================================================================


class TestOpenAIAdapter:
    """OpenAIAdapter 单元测试。"""

    def _make_adapter(self, **kwargs):
        defaults = {
            "api_key": "test-key",
            "model": "gpt-4o",
            "timeout": 30.0,
        }
        defaults.update(kwargs)
        return OpenAIAdapter(**defaults)

    def test_chat_success(self, mock_httpx_client):
        """chat 成功返回标准化 LLMResponse。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.chat([{"role": "user", "content": "Hi"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello!"
        assert result.provider == "openai"
        assert result.model == "gpt-4o"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.total_tokens == 15
        assert result.meta["finish_reason"] == "stop"

        # 验证请求 payload
        call_args = client.post.call_args
        assert call_args[0][0] == "/chat/completions"
        payload = call_args[1]["json"]
        assert payload["model"] == "gpt-4o"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2000

    def test_chat_with_system_message(self, mock_httpx_client):
        """system message 正确透传。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            adapter.chat([
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hi"},
            ])

        payload = client.post.call_args[1]["json"]
        messages = payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_chat_timeout_raises_llm_timeout(self, mock_httpx_client):
        """httpx.TimeoutException 被翻译为 LLMTimeoutError。"""
        client, _ = mock_httpx_client
        client.post.side_effect = httpx.TimeoutException("timed out")

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMTimeoutError) as exc_info:
                adapter.chat([{"role": "user", "content": "test"}])
            assert "openai" in str(exc_info.value)

    def test_chat_401_raises_auth_error(self, mock_httpx_client):
        """401 被翻译为 LLMAuthenticationError。"""
        client, _ = mock_httpx_client
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.json.return_value = {"error": {"message": "bad key", "code": "invalid_api_key"}}
        exc = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=error_response,
        )
        client.post.side_effect = exc

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMAuthenticationError) as exc_info:
                adapter.chat([{"role": "user", "content": "test"}])
            assert exc_info.value.code == "invalid_api_key"

    def test_chat_429_raises_rate_limit(self, mock_httpx_client):
        """429 被翻译为 LLMRateLimitError（可重试）。"""
        client, _ = mock_httpx_client
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.json.return_value = {"error": {"message": "rate limit"}}
        exc = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=error_response,
        )
        client.post.side_effect = exc

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMRateLimitError):
                adapter.chat([{"role": "user", "content": "test"}])

    def test_chat_500_raises_service_unavailable(self, mock_httpx_client):
        """5xx 被翻译为 LLMServiceUnavailableError（可重试）。"""
        client, _ = mock_httpx_client
        error_response = MagicMock()
        error_response.status_code = 503
        error_response.json.return_value = {"error": {"message": "overloaded"}}
        exc = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=error_response,
        )
        client.post.side_effect = exc

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMServiceUnavailableError):
                adapter.chat([{"role": "user", "content": "test"}])

    def test_embed_success(self, mock_httpx_client):
        """embed 返回向量列表。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.embed(["hello", "world"])

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payload = client.post.call_args[1]["json"]
        assert payload["input"] == ["hello", "world"]

    def test_health_check_healthy(self, mock_httpx_client):
        """健康检查 200 → HEALTHY。"""
        client, response = mock_httpx_client
        response.status_code = 200

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            assert adapter.health_check() == HealthStatus.HEALTHY

    def test_health_check_unhealthy(self, mock_httpx_client):
        """健康检查 503 → UNHEALTHY。"""
        client, response = mock_httpx_client
        response.status_code = 503

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            assert adapter.health_check() == HealthStatus.UNHEALTHY

    def test_complete_delegates_to_chat(self, mock_httpx_client):
        """complete() 默认实现委托给 chat()。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "choices": [{"message": {"content": "Done"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.complete("Say hello", system="Be brief")

        assert isinstance(result, LLMResponse)
        assert result.content == "Done"
        payload = client.post.call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Say hello"

    def test_timeout_passed_to_client(self):
        """timeout 参数正确传递到 httpx.Client。"""
        with patch("httpx.Client") as MockClient:
            self._make_adapter(timeout=42.0)
            assert MockClient.call_args[1]["timeout"] == 42.0


# =============================================================================
# Anthropic Adapter Tests
# =============================================================================


class TestAnthropicAdapter:
    """AnthropicAdapter 单元测试。"""

    def _make_adapter(self, **kwargs):
        defaults = {
            "api_key": "test-key",
            "model": "claude-3-opus-20240229",
        }
        defaults.update(kwargs)
        return AnthropicAdapter(**defaults)

    def test_chat_success(self, mock_httpx_client):
        """chat 成功返回标准化 LLMResponse。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "content": [{"type": "text", "text": "Claude says hi!"}],
            "usage": {"input_tokens": 8, "output_tokens": 4},
            "stop_reason": "end_turn",
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.chat([{"role": "user", "content": "Hello"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Claude says hi!"
        assert result.provider == "anthropic"
        assert result.model == "claude-3-opus-20240229"
        assert result.usage.prompt_tokens == 8
        assert result.usage.completion_tokens == 4
        assert result.usage.total_tokens == 12
        assert result.meta["stop_reason"] == "end_turn"

        payload = client.post.call_args[1]["json"]
        assert payload["model"] == "claude-3-opus-20240229"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        assert "system" not in payload

    def test_chat_system_extracted(self, mock_httpx_client):
        """system message 被提取到顶层 system 参数。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "content": [{"type": "text", "text": "OK"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            adapter.chat([
                {"role": "system", "content": "Be concise"},
                {"role": "user", "content": "Hi"},
            ])

        payload = client.post.call_args[1]["json"]
        assert payload["system"] == "Be concise"
        # system message 不应出现在 messages 列表中
        assert all(m["role"] != "system" for m in payload["messages"])

    def test_embed_not_implemented(self, mock_httpx_client):
        """Anthropic 暂不支持 embed。"""
        client, _ = mock_httpx_client
        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMNotImplementedError):
                adapter.embed(["hello"])

    def test_error_translation(self, mock_httpx_client):
        """Anthropic 错误翻译。"""
        client, _ = mock_httpx_client
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.json.return_value = {"error": {"message": "invalid", "type": "authentication_error"}}
        exc = httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=error_response,
        )
        client.post.side_effect = exc

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            with pytest.raises(LLMAuthenticationError) as exc_info:
                adapter.chat([{"role": "user", "content": "x"}])
            assert exc_info.value.code == "authentication_error"


# =============================================================================
# Gemini Adapter Tests
# =============================================================================


class TestGeminiAdapter:
    """GeminiAdapter 单元测试。"""

    def _make_adapter(self, **kwargs):
        defaults = {
            "api_key": "test-key",
            "model": "gemini-1.5-pro-latest",
        }
        defaults.update(kwargs)
        return GeminiAdapter(**defaults)

    def test_chat_success(self, mock_httpx_client):
        """chat 成功返回标准化 LLMResponse。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Gemini here!"}],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 3,
                "totalTokenCount": 8,
            },
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.chat([{"role": "user", "content": "Hey"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Gemini here!"
        assert result.provider == "gemini"
        assert result.model == "gemini-1.5-pro-latest"
        assert result.usage.prompt_tokens == 5
        assert result.usage.completion_tokens == 3
        assert result.usage.total_tokens == 8
        assert result.meta["finish_reason"] == "STOP"

        payload = client.post.call_args[1]["json"]
        assert payload["contents"][0]["role"] == "user"
        assert payload["contents"][0]["parts"][0]["text"] == "Hey"

    def test_chat_system_instruction(self, mock_httpx_client):
        """system message 映射为 system_instruction。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}],
            "usageMetadata": {},
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            adapter.chat([
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ])

        payload = client.post.call_args[1]["json"]
        assert "system_instruction" in payload
        assert payload["system_instruction"]["parts"][0]["text"] == "You are helpful"

    def test_chat_assistant_role_mapping(self, mock_httpx_client):
        """assistant role 映射为 Gemini 的 model role。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}],
            "usageMetadata": {},
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            adapter.chat([
                {"role": "user", "content": "Q"},
                {"role": "assistant", "content": "A"},
            ])

        payload = client.post.call_args[1]["json"]
        roles = [c["role"] for c in payload["contents"]]
        assert roles == ["user", "model"]

    def test_embed_success(self, mock_httpx_client):
        """embed 返回向量列表。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "embeddings": [
                {"values": [0.1, 0.2]},
                {"values": [0.3, 0.4]},
            ]
        }

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            result = adapter.embed(["a", "b"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        payload = client.post.call_args[1]["json"]
        assert len(payload["requests"]) == 2

    def test_health_check_healthy(self, mock_httpx_client):
        """健康检查 200 → HEALTHY。"""
        client, response = mock_httpx_client
        response.status_code = 200

        with patch("httpx.Client", return_value=client):
            adapter = self._make_adapter()
            assert adapter.health_check() == HealthStatus.HEALTHY


# =============================================================================
# Factory Tests
# =============================================================================


class TestFactory:
    """Factory 统一创建入口测试。"""

    def test_create_openai(self):
        """通过 factory 创建 OpenAI adapter。"""
        with patch("httpx.Client"):
            adapter = create_adapter("openai", api_key="k", model="gpt-4")
        assert isinstance(adapter, OpenAIAdapter)
        assert adapter.provider_name == "openai"
        assert adapter.model == "gpt-4"

    def test_create_anthropic(self):
        """通过 factory 创建 Anthropic adapter。"""
        with patch("httpx.Client"):
            adapter = create_adapter("anthropic", api_key="k")
        assert isinstance(adapter, AnthropicAdapter)
        assert adapter.provider_name == "anthropic"

    def test_create_gemini(self):
        """通过 factory 创建 Gemini adapter。"""
        with patch("httpx.Client"):
            adapter = create_adapter("gemini", api_key="k")
        assert isinstance(adapter, GeminiAdapter)
        assert adapter.provider_name == "gemini"

    def test_create_kimi_uses_openai_class(self):
        """kimi alias 映射到 OpenAIAdapter。"""
        with patch("httpx.Client"):
            adapter = create_adapter("kimi", api_key="k")
        assert isinstance(adapter, OpenAIAdapter)
        assert adapter.provider_name == "kimi"

    def test_create_unknown_raises(self):
        """未知 provider 抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的 provider"):
            create_adapter("unknown", api_key="k")

    def test_list_providers(self):
        """list_providers 返回支持的名称。"""
        providers = list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "gemini" in providers
        assert "kimi" in providers
        assert "deepseek" in providers

    def test_register_provider(self):
        """register_provider 支持动态注册。"""
        class DummyAdapter(BaseLLMAdapter):
            def chat(self, messages, **kwargs):
                pass

            def embed(self, texts, **kwargs):
                pass

            def health_check(self):
                return HealthStatus.HEALTHY

        register_provider("dummy", DummyAdapter)
        with patch("httpx.Client"):
            adapter = create_adapter("dummy", api_key="k")
        assert isinstance(adapter, DummyAdapter)


# =============================================================================
# Retry Policy Tests
# =============================================================================


class TestRetryPolicy:
    """Tenacity 重试策略测试。"""

    def test_retry_on_rate_limit(self):
        """LLMRateLimitError 触发重试。"""
        call_count = 0

        @with_llm_retry(max_retries=3, backoff_initial=0.01, backoff_max=0.1)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMRateLimitError("rate limited")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_retry_on_service_unavailable(self):
        """LLMServiceUnavailableError 触发重试。"""
        call_count = 0

        @with_llm_retry(max_retries=2, backoff_initial=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMServiceUnavailableError("down")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 2

    def test_retry_on_timeout(self):
        """LLMTimeoutError 触发重试。"""
        call_count = 0

        @with_llm_retry(max_retries=2, backoff_initial=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMTimeoutError("timeout")
            return "ok"

        result = flaky()
        assert result == "ok"

    def test_no_retry_on_auth_error(self):
        """LLMAuthenticationError 不触发重试。"""
        call_count = 0

        @with_llm_retry(max_retries=3, backoff_initial=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise LLMAuthenticationError("bad key")

        with pytest.raises(LLMAuthenticationError):
            always_fail()
        assert call_count == 1

    def test_no_retry_on_bad_request(self):
        """LLMBadRequestError 不触发重试。"""
        call_count = 0

        @with_llm_retry(max_retries=3, backoff_initial=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise LLMBadRequestError("bad param")

        with pytest.raises(LLMBadRequestError):
            always_fail()
        assert call_count == 1

    def test_retryable_exceptions_tuple(self):
        """RETRYABLE_EXCEPTIONS 包含正确类型。"""
        assert LLMTimeoutError in RETRYABLE_EXCEPTIONS
        assert LLMRateLimitError in RETRYABLE_EXCEPTIONS
        assert LLMServiceUnavailableError in RETRYABLE_EXCEPTIONS
        assert LLMAuthenticationError not in RETRYABLE_EXCEPTIONS


# =============================================================================
# Base Adapter Tests
# =============================================================================


class TestBaseLLMAdapter:
    """BaseLLMAdapter 默认行为测试。"""

    def test_complete_builds_messages(self, mock_httpx_client):
        """complete() 默认实现正确构建 messages 列表。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        with patch("httpx.Client", return_value=client):
            adapter = OpenAIAdapter(api_key="k")
            result = adapter.complete("Hello", system="Be nice")

        assert isinstance(result, LLMResponse)
        payload = client.post.call_args[1]["json"]
        assert payload["messages"] == [
            {"role": "system", "content": "Be nice"},
            {"role": "user", "content": "Hello"},
        ]

    def test_complete_without_system(self, mock_httpx_client):
        """complete() 无 system 时仅包含 user message。"""
        client, response = mock_httpx_client
        response.json.return_value = {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        with patch("httpx.Client", return_value=client):
            adapter = OpenAIAdapter(api_key="k")
            adapter.complete("Hello")

        payload = client.post.call_args[1]["json"]
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]

    def test_list_models_default_empty(self):
        """默认 list_models 返回空列表。"""
        adapter = OpenAIAdapter(api_key="k")
        assert adapter.list_models() == []

    def test_repr(self):
        """__repr__ 包含关键信息。"""
        adapter = OpenAIAdapter(api_key="k", model="gpt-4o")
        r = repr(adapter)
        assert "OpenAIAdapter" in r
        assert "openai" in r
        assert "gpt-4o" in r

    def test_generate_stream_not_implemented(self):
        """默认 generate_stream 抛出 NotImplementedError。"""
        adapter = OpenAIAdapter(api_key="k")
        with pytest.raises(NotImplementedError):
            next(adapter.generate_stream([{"role": "user", "content": "hi"}]))


# =============================================================================
# Integration Smoke Tests
# =============================================================================


class TestIntegrationSmoke:
    """集成冒烟测试：验证所有 adapter 可被实例化并遵守接口契约。"""

    def test_all_adapters_implement_base(self):
        """所有具体 adapter 均为 BaseLLMAdapter 子类。"""
        assert issubclass(OpenAIAdapter, BaseLLMAdapter)
        assert issubclass(AnthropicAdapter, BaseLLMAdapter)
        assert issubclass(GeminiAdapter, BaseLLMAdapter)

    def test_all_adapters_have_chat_embed_health(self):
        """所有 adapter 均实现 chat、embed、health_check。"""
        for cls in (OpenAIAdapter, AnthropicAdapter, GeminiAdapter):
            assert hasattr(cls, "chat")
            assert hasattr(cls, "embed")
            assert hasattr(cls, "health_check")

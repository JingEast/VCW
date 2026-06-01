"""测试 AnthropicAdapter 生产调用链集成。"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from llm.adapter import AnthropicAdapter, LLMResponse
from llm.adapter.exceptions import LLMNotImplementedError, LLMAuthenticationError


@pytest.fixture
def adapter():
    return AnthropicAdapter(api_key="test-key", model="claude-3-opus")


class TestAnthropicAdapterChat:
    """验证 AnthropicAdapter.chat() 返回统一 LLMResponse。"""

    def test_chat_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "hello from claude"}],
            "usage": {"input_tokens": 8, "output_tokens": 4},
            "stop_reason": "end_turn",
        }
        adapter._client = MagicMock()
        adapter._client.post.return_value = mock_resp

        response = adapter.chat([{"role": "user", "content": "hi"}])
        assert isinstance(response, LLMResponse)
        assert response.content == "hello from claude"
        assert response.provider == "anthropic"
        assert response.model == "claude-3-opus"
        assert response.usage.prompt_tokens == 8
        assert response.usage.completion_tokens == 4
        assert response.usage.total_tokens == 12

    def test_chat_extracts_system_message(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {},
        }
        adapter._client = MagicMock()
        adapter._client.post.return_value = mock_resp

        adapter.chat([
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ])
        _, kwargs = adapter._client.post.call_args
        payload = kwargs["json"]
        assert payload["system"] == "sys"
        assert all(m["role"] != "system" for m in payload["messages"])

    def test_chat_auth_error(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "invalid key", "type": "authentication_error"}}
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "invalid key", request=MagicMock(), response=mock_resp
        )
        adapter._client = MagicMock()
        adapter._client.post.return_value = mock_resp

        with pytest.raises(LLMAuthenticationError):
            adapter.chat([{"role": "user", "content": "hi"}])


class TestAnthropicAdapterEmbed:
    """验证 AnthropicAdapter.embed() 抛出 NotImplementedError。"""

    def test_embed_not_implemented(self, adapter):
        with pytest.raises(LLMNotImplementedError):
            adapter.embed(["hello"])

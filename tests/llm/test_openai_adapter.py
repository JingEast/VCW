"""测试 OpenAIAdapter 生产调用链集成。"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from llm.adapter import OpenAIAdapter, LLMResponse
from llm.adapter.exceptions import LLMRateLimitError, LLMTimeoutError


@pytest.fixture
def adapter():
    return OpenAIAdapter(api_key="test-key", model="gpt-4o")


class TestOpenAIAdapterChat:
    """验证 OpenAIAdapter.chat() 返回统一 LLMResponse。"""

    def test_chat_success(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        adapter._client = MagicMock()
        adapter._client.post.return_value = mock_resp

        response = adapter.chat([{"role": "user", "content": "hi"}])
        assert isinstance(response, LLMResponse)
        assert response.content == "hello"
        assert response.provider == "openai"
        assert response.model == "gpt-4o"
        assert response.usage.total_tokens == 15
        assert response.meta["finish_reason"] == "stop"

    def test_chat_rate_limit(self, adapter):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": {"message": "rate limit", "code": "rate_limit"}}
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limit", request=MagicMock(), response=mock_resp
        )
        adapter._client = MagicMock()
        adapter._client.post.return_value = mock_resp

        with pytest.raises(LLMRateLimitError):
            adapter.chat([{"role": "user", "content": "hi"}])

    def test_chat_timeout(self, adapter):
        adapter._client = MagicMock()
        adapter._client.post.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(LLMTimeoutError):
            adapter.chat([{"role": "user", "content": "hi"}])


class TestOpenAIAdapterGenerateStream:
    """验证 OpenAIAdapter.generate_stream() 流式输出。"""

    def test_generate_stream_yields_llmresponse(self, adapter):
        adapter._client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        lines = [
            'data: {"choices": [{"delta": {"content": "He"}}]}',
            'data: {"choices": [{"delta": {"content": "llo"}}]}',
            "data: [DONE]",
        ]
        mock_stream.iter_lines.return_value = lines
        mock_stream.raise_for_status = MagicMock()
        adapter._client.stream.return_value = mock_stream

        chunks = list(adapter.generate_stream([{"role": "user", "content": "hi"}]))
        # 2 个文本片段 + 1 个结束标记
        assert len(chunks) == 3
        assert chunks[0].content == "He"
        assert chunks[1].content == "llo"
        assert chunks[2].content == ""
        assert chunks[2].usage.total_tokens == 0

    def test_generate_stream_uses_httpx_stream(self, adapter):
        adapter._client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.iter_lines.return_value = ["data: [DONE]"]
        mock_stream.raise_for_status = MagicMock()
        adapter._client.stream.return_value = mock_stream

        list(adapter.generate_stream([{"role": "user", "content": "hi"}]))
        adapter._client.stream.assert_called_once()
        args, _ = adapter._client.stream.call_args
        assert args[0] == "POST"
        assert args[1] == "/chat/completions"

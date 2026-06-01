"""测试 LLMResponse / TokenUsage DTO 契约。"""

from __future__ import annotations

import pytest

from llm.adapter.base import LLMResponse, TokenUsage


class TestTokenUsage:
    """TokenUsage 不可变数据类测试。"""

    def test_defaults(self):
        u = TokenUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_fields_set(self):
        u = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert u.prompt_tokens == 10
        assert u.completion_tokens == 20
        assert u.total_tokens == 30

    def test_immutable(self):
        u = TokenUsage(prompt_tokens=1)
        with pytest.raises(AttributeError):
            u.prompt_tokens = 2


class TestLLMResponse:
    """LLMResponse 不可变数据类测试。"""

    def test_required_fields(self):
        r = LLMResponse(
            content="hello",
            provider="openai",
            model="gpt-4o",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            latency_ms=123.4,
        )
        assert r.content == "hello"
        assert r.provider == "openai"
        assert r.model == "gpt-4o"
        assert r.usage.total_tokens == 10
        assert r.latency_ms == 123.4
        assert r.meta == {}
        assert r.raw_response is None

    def test_optional_meta_and_raw(self):
        raw = {"id": "chatcmpl-xxx"}
        r = LLMResponse(
            content="world",
            provider="anthropic",
            model="claude-3",
            usage=TokenUsage(),
            latency_ms=0.0,
            meta={"stop_reason": "end_turn"},
            raw_response=raw,
        )
        assert r.meta["stop_reason"] == "end_turn"
        assert r.raw_response == raw

    def test_immutable(self):
        r = LLMResponse(
            content="x",
            provider="p",
            model="m",
            usage=TokenUsage(),
            latency_ms=0.0,
        )
        with pytest.raises(AttributeError):
            r.content = "y"

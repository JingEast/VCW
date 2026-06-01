"""测试 Provider Fallback 策略。"""

from __future__ import annotations

from llm.fallback.chain_strategy import ChainFallbackStrategy
from llm.fallback.base import FallbackResult


class TestChainFallbackStrategy:
    """验证链式 fallback 决策逻辑。"""

    def test_decide_next_provider(self):
        strategy = ChainFallbackStrategy(priority=["openai", "kimi", "deepseek"])
        result = strategy.decide("openai", ["openai", "kimi", "deepseek"])
        assert isinstance(result, FallbackResult)
        assert result.provider == "kimi"
        assert "openai 失败" in result.reason

    def test_decide_skips_unavailable(self):
        strategy = ChainFallbackStrategy(priority=["openai", "kimi", "deepseek"])
        result = strategy.decide("openai", ["kimi", "deepseek"])
        assert result.provider == "kimi"

    def test_decide_exhausted_returns_none(self):
        strategy = ChainFallbackStrategy(priority=["openai"])
        result = strategy.decide("openai", ["openai"])
        assert result is None

    def test_decide_unknown_failed_provider(self):
        strategy = ChainFallbackStrategy(priority=["openai", "kimi"])
        result = strategy.decide("azure", ["openai", "kimi"])
        assert result.provider == "openai"

    def test_record_result_updates_history(self):
        strategy = ChainFallbackStrategy(priority=["openai"])
        strategy.record_result("openai", True, 120.0)
        assert "openai" in strategy._history
        assert len(strategy._history["openai"]) == 1
        assert strategy._history["openai"][0] == (True, 120.0)

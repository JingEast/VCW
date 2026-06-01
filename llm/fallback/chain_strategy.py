"""链式 Fallback 策略。"""

from __future__ import annotations

from typing import Any, List, Optional

from .base import BaseFallbackStrategy, FallbackResult


class ChainFallbackStrategy(BaseFallbackStrategy):
    """链式依次尝试策略。

    配置示例：
        strategy = ChainFallbackStrategy(priority=["kimi", "deepseek", "azure"])
    """

    def __init__(self, priority: List[str]) -> None:
        self.priority = priority
        self._history: dict[str, list[tuple[bool, float]]] = {}

    def decide(
        self,
        failed_provider: str,
        available_providers: List[str],
        error: Optional[Exception] = None,
    ) -> Optional[FallbackResult]:
        # 找到失败 provider 在优先级列表中的位置，返回下一个
        try:
            idx = self.priority.index(failed_provider)
        except ValueError:
            idx = -1

        for candidate in self.priority[idx + 1:]:
            if candidate in available_providers:
                result = FallbackResult(
                    provider=candidate,
                    reason=f"{failed_provider} 失败，链式降级到 {candidate}",
                    attempts=1,
                )
                self._trace_fallback(failed_provider, result)
                return result
        self._trace_fallback(failed_provider, None)
        return None

    def _trace_fallback(self, failed_provider: str, result: Optional[FallbackResult]) -> None:
        """记录 fallback span event（若当前存在 otel span）。"""
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and getattr(span, "is_recording", lambda: False)():
                attrs: dict[str, Any] = {
                    "fallback.from_provider": failed_provider,
                    "fallback.result": "success" if result is not None else "exhausted",
                }
                if result is not None:
                    attrs["fallback.to_provider"] = result.provider
                    attrs["fallback.reason"] = result.reason
                span.add_event("llm.fallback", attrs)
        except ImportError:
            pass

    def record_result(
        self,
        provider: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        self._history.setdefault(provider, []).append((success, latency_ms))

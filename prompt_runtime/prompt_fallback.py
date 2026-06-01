"""Prompt Fallback 策略 —— 模型失败自动切换与降级。

职责：
  1. 主模型失败时，按优先级自动切换到备用模型。
  2. 所有模型都失败时，执行降级策略（返回预设内容或空响应）。
  3. 与 Retry 策略配合，实现多层容错。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple


@dataclass
class DegradeContent:
    """降级内容模板。"""

    content: str = ""
    meta: str = "degraded"
    success: bool = True


class IPromptFallbackStrategy(ABC):
    """Fallback 策略接口。"""

    @abstractmethod
    def execute(
        self,
        primary_fn: Callable,
        fallback_chain: List[Callable],
        degrade_content: Optional[DegradeContent] = None,
    ) -> Tuple[bool, Any]:
        """执行 fallback 链，返回 (是否成功, 结果)。"""


class ModelFallbackStrategy(IPromptFallbackStrategy):
    """模型级 Fallback 策略。

    执行顺序：
      primary_fn → fallback_chain[0] → fallback_chain[1] → ... → degrade
    """

    def execute(
        self,
        primary_fn: Callable,
        fallback_chain: List[Callable],
        degrade_content: Optional[DegradeContent] = None,
    ) -> Tuple[bool, Any]:
        errors: List[str] = []

        for fn, label in self._build_chain(primary_fn, fallback_chain):
            try:
                result = fn()
                return True, result
            except Exception as exc:
                errors.append(f"{label}: {exc}")

        # 全部失败，执行降级
        if degrade_content is not None:
            return True, degrade_content

        # 无降级策略，汇总错误抛出
        raise FallbackExhaustedError(
            "All fallback models exhausted",
            errors=errors,
        )

    @staticmethod
    def _build_chain(
        primary: Callable, fallbacks: List[Callable]
    ) -> List[Tuple[Callable, str]]:
        chain = [(primary, "primary")]
        for i, fn in enumerate(fallbacks):
            chain.append((fn, f"fallback_{i}"))
        return chain


class FallbackExhaustedError(Exception):
    """所有 fallback 模型均已耗尽。"""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)

    def __str__(self) -> str:
        base = self.message
        if self.errors:
            base += " | " + "; ".join(self.errors)
        return base

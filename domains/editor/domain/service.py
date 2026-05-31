"""
Editor Domain — Domain Service
==============================

精修编辑器领域的无状态业务逻辑服务。
"""

from typing import Tuple

from .value_object import DeAIPrompt


class DiffEngine:
    """
    文本差异引擎（领域服务）。

    计算两段文本的差异。当前为简化实现，仅返回行级差异描述。
    """

    @staticmethod
    def compute_diff(original: str, edited: str) -> Tuple[int, int, int]:
        """
        计算文本差异统计。

        Returns:
            (added_lines, removed_lines, unchanged_lines)
        """
        orig_lines = original.splitlines()
        edit_lines = edited.splitlines()

        # 简化统计：基于长度变化给出大致增减行数
        length_delta = len(edited) - len(original)
        avg_line_length = max(len(original) // max(len(orig_lines), 1), 50)

        estimated_changed = abs(length_delta) // avg_line_length
        unchanged = max(len(orig_lines), len(edit_lines)) - estimated_changed

        if length_delta >= 0:
            return estimated_changed, 0, max(0, unchanged)
        else:
            return 0, estimated_changed, max(0, unchanged)

    @staticmethod
    def has_changes(original: str, edited: str) -> bool:
        """判断两段文本是否有实质差异。"""
        return original.strip() != edited.strip()


class DeAIOptimizer:
    """
    去 AI 味优化器（领域服务）。

    负责构建优化提示词。实际的 LLM 调用由应用层委托 Generation Domain 完成。
    """

    def __init__(self):
        self._prompt = DeAIPrompt()

    def build_prompt(self, content: str) -> str:
        """构建用于去 AI 味精修的优化提示词。"""
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        return self._prompt.render(content)

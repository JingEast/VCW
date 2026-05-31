"""
Prompt Domain — Value Object
============================

Prompt 工程领域的值对象集合。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptContext:
    """
    Prompt 上下文（值对象）。

    组装 prompt 所需的全部输入参数。
    """

    topic: str
    audience: str = "港宝家长"
    core_data: str = ""
    policy_points: str = ""
    hidden_path: str = ""
    call_to_action: str = ""
    sample_ref: str = ""
    extra_requirements: str = ""
    scene: str = ""
    memory_text: str = ""
    knowledge_text: str = ""

    def __post_init__(self):
        if not self.topic or not self.topic.strip():
            raise ValueError("PromptContext topic cannot be empty")


@dataclass(frozen=True)
class PromptSection:
    """Prompt 段落（值对象）。"""

    name: str
    content: str


@dataclass(frozen=True)
class SampleCopy:
    """参考样本文案（值对象）。"""

    name: str
    content: str

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("SampleCopy name cannot be empty")


@dataclass(frozen=True)
class RenderedPrompt:
    """渲染后的提示词（值对象）。"""

    system: str
    user: str

    @property
    def system_length(self) -> int:
        return len(self.system)

    @property
    def user_length(self) -> int:
        return len(self.user)

"""
Editor Domain — Value Object
============================

精修编辑器领域的值对象集合。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DraftStatus(Enum):
    """草稿状态枚举（值对象）。"""

    DRAFT = "draft"
    EDITED = "edited"
    FINAL = "final"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DraftId:
    """草稿唯一标识（值对象）。"""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("DraftId cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class EditRecord:
    """
    编辑记录（值对象）。

    不可变，每次编辑产生一条新记录。
    """

    timestamp: str
    note: str
    before_length: int
    after_length: int

    @property
    def length_delta(self) -> int:
        return self.after_length - self.before_length


@dataclass(frozen=True)
class DeAIPrompt:
    """去 AI 味优化指令模板（值对象）。"""

    template: str = (
        "你是一位资深短视频文案编辑，擅长将AI生成的文案润色为真人博主的口语表达。\n\n"
        "请对以下文案进行'去AI味'精修，要求：\n"
        "1. 打破完美逻辑——加入一些口语停顿、自我修正、重复强调\n"
        "2. 长短句交错——不要用整齐的排比，让句子长短不一\n"
        "3. 情绪化表达——该惊叹的地方用'哇''天哪''说实话'等感叹\n"
        "4. 人称拉近——多用'咱们''你家孩子''各位家长'拉近距离\n"
        "5. 去学术化——把'因此''综上所述'换成'说白了''老实说'\n"
        "6. 加入不完美的真实感——偶尔说'这个...''那个...''我直说了啊'\n\n"
        "注意：保留所有核心数据和政策信息，只修改表达方式。\n\n"
        "【原文案】\n{content}\n\n"
        "请直接输出精修后的文案，不要加任何解释。"
    )

    def render(self, content: str) -> str:
        return self.template.format(content=content)

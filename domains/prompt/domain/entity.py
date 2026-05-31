"""
Prompt Domain — Entity
======================

Prompt 工程领域的核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List



@dataclass
class PromptTemplate:
    """
    Prompt 模板实体。

    表示一个可渲染的 system prompt 模板，支持变量插值。

    Attributes:
        name: 模板名称（唯一标识）。
        system_template: 模板字符串（含 {memory_section} / {knowledge_section} 等占位符）。
        version: 版本号。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    name: str
    system_template: str
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("PromptTemplate name cannot be empty")
        if not self.system_template or not self.system_template.strip():
            raise ValueError("PromptTemplate system_template cannot be empty")

    def render(self, **kwargs) -> str:
        """渲染模板，替换占位符。"""
        try:
            return self.system_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    def update_template(self, new_template: str) -> None:
        """更新模板内容。"""
        self.system_template = new_template
        self.updated_at = datetime.now()

    def extract_placeholders(self) -> List[str]:
        """提取模板中的所有占位符变量名。"""
        import re

        return re.findall(r"\{(\w+)\}", self.system_template)

    @property
    def is_valid(self) -> bool:
        """检查模板是否包含必要的占位符。"""
        required = {"memory_section", "knowledge_section"}
        placeholders = set(self.extract_placeholders())
        return required.issubset(placeholders)

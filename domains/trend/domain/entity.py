"""
Trend Domain — Entity
=====================

热点发现领域的核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .value_object import Category, TrendId


@dataclass
class Trend:
    """
    热点实体。

    表示一条教育领域的热点话题，包含标题、摘要、来源、时效性等信息。

    Attributes:
        id: 唯一标识（TrendId）。
        title: 标题（必填）。
        summary: 摘要。
        url: 来源链接。
        published_at: 发布时间（ISO 格式字符串）。
        heat: 热度值（0-100）。
        category: 分类（Category 值对象）。
        tags: 标签列表。
        is_selected: 是否已被选用。
        selected_at: 选用时间。
        is_archived: 是否已归档。
    """

    id: TrendId
    title: str
    summary: str = ""
    url: str = ""
    published_at: str = ""
    heat: int = 0
    category: Category = field(default_factory=lambda: Category("其他"))
    tags: List[str] = field(default_factory=list)
    is_selected: bool = False
    selected_at: Optional[str] = None
    is_archived: bool = False

    def __post_init__(self):
        if not self.title or not self.title.strip():
            raise ValueError("Trend title cannot be empty")
        if self.heat < 0 or self.heat > 100:
            raise ValueError("Trend heat must be between 0 and 100")

    def select(self) -> None:
        """标记为已选用。"""
        self.is_selected = True
        self.selected_at = datetime.now().isoformat()

    def archive(self) -> None:
        """归档。"""
        self.is_archived = True

    def unarchive(self) -> None:
        """取消归档。"""
        self.is_archived = False

    def update_heat(self, new_heat: int) -> None:
        """更新热度值。"""
        if new_heat < 0 or new_heat > 100:
            raise ValueError("Heat must be between 0 and 100")
        self.heat = new_heat

    def add_tag(self, tag: str) -> None:
        """添加标签（去重）。"""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """移除标签。"""
        if tag in self.tags:
            self.tags.remove(tag)

    @property
    def is_fresh(self) -> bool:
        """判断是否为新鲜热点（7 天内）。"""
        if not self.published_at:
            return False
        try:
            published = datetime.fromisoformat(self.published_at)
            delta = datetime.now() - published
            return delta.days <= 7
        except ValueError:
            return False

    @property
    def is_expired(self) -> bool:
        """判断是否已过期（超过 365 天）。"""
        if not self.published_at:
            return True
        try:
            published = datetime.fromisoformat(self.published_at)
            delta = datetime.now() - published
            return delta.days > 365
        except ValueError:
            return True

    @property
    def is_stale(self) -> bool:
        """判断是否已陈旧（超过 90 天）。"""
        if not self.published_at:
            return True
        try:
            published = datetime.fromisoformat(self.published_at)
            delta = datetime.now() - published
            return delta.days > 90
        except ValueError:
            return True

"""
Editor Domain — Entity
======================

精修编辑器领域的核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from .value_object import DraftId, DraftStatus, EditRecord


@dataclass
class Draft:
    """
    草稿实体。

    表示一篇需要精修的文案草稿，包含原始内容、精修内容、编辑历史和状态。

    Attributes:
        id: 唯一标识（DraftId）。
        topic: 主题。
        original_content: 原始文案内容。
        edited_content: 精修后的文案内容。
        status: 草稿状态。
        source_filepath: 来源文件路径。
        meta: 元信息。
        edit_history: 编辑历史记录列表。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: DraftId
    topic: str
    original_content: str
    edited_content: str = ""
    status: DraftStatus = field(default_factory=lambda: DraftStatus.DRAFT)
    source_filepath: str = ""
    meta: str = ""
    edit_history: List[EditRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.topic or not self.topic.strip():
            raise ValueError("Draft topic cannot be empty")
        if not self.original_content or not self.original_content.strip():
            raise ValueError("Draft original_content cannot be empty")

    def edit(self, new_content: str, note: str = "") -> None:
        """
        更新精修内容。

        记录编辑历史，更新状态为 EDITED。
        """
        record = EditRecord(
            timestamp=datetime.now().isoformat(),
            note=note,
            before_length=len(self.edited_content),
            after_length=len(new_content),
        )
        self.edit_history.append(record)
        self.edited_content = new_content
        self.status = DraftStatus.EDITED
        self.updated_at = datetime.now()

    def finalize(self) -> None:
        """
        定稿。

        将状态变更为 FINAL。定稿后建议不再修改。
        """
        if self.status == DraftStatus.FINAL:
            return
        self.status = DraftStatus.FINAL
        self.updated_at = datetime.now()

    def revert_to_original(self) -> None:
        """放弃所有精修，回退到原始内容。"""
        self.edited_content = self.original_content
        self.status = DraftStatus.DRAFT
        self.updated_at = datetime.now()

    def get_diff(self) -> tuple[str, str]:
        """返回 (original, edited) 元组。"""
        return self.original_content, self.edited_content

    @property
    def is_finalized(self) -> bool:
        return self.status == DraftStatus.FINAL

    @property
    def current_content(self) -> str:
        """返回当前生效的内容（精修版优先，否则原始版）。"""
        return self.edited_content or self.original_content

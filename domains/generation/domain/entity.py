"""
Generation Domain — Entity
==========================

文案生成领域的核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .value_object import QualityReport, GenerationParams


@dataclass
class Copy:
    """
    文案实体。

    表示一次生成操作产出的最终文案内容及其元信息。

    Attributes:
        id: 唯一标识（UUID）。
        topic: 文案主题。
        content: 生成的正文内容。
        meta: 生成元信息（模型、耗时等）。
        quality_report: 质量检查报告。
        created_at: 创建时间。
    """

    id: str
    topic: str
    content: str
    meta: str = ""
    quality_report: Optional[QualityReport] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.id:
            raise ValueError("Copy id cannot be empty")
        if not self.topic:
            raise ValueError("Copy topic cannot be empty")

    def is_passed(self, strict_mode: bool = False) -> bool:
        """根据质量报告判断是否通过。"""
        if self.quality_report is None:
            return True
        return self.quality_report.is_passed(strict_mode)

    def update_content(self, new_content: str) -> None:
        """更新文案内容（精修场景）。"""
        self.content = new_content


@dataclass
class GenerationTask:
    """
    生成任务实体。

    用于追踪异步或批量生成任务的状态。

    Attributes:
        id: 唯一标识。
        params: 生成参数。
        status: 任务状态（pending / running / completed / failed）。
        result: 生成结果（Copy 列表）。
        error_message: 失败时的错误信息。
        created_at: 创建时间。
        completed_at: 完成时间。
    """

    id: str
    params: GenerationParams
    status: str = "pending"
    result: List[Copy] = field(default_factory=list)
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def mark_running(self) -> None:
        self.status = "running"

    def mark_completed(self, copies: List[Copy]) -> None:
        self.status = "completed"
        self.result = copies
        self.completed_at = datetime.now()

    def mark_failed(self, message: str) -> None:
        self.status = "failed"
        self.error_message = message
        self.completed_at = datetime.now()

"""
Generation Domain — Plain Entities
==================================

与 ORM 解耦的领域实体，使用 @dataclass 定义，
确保 domain 可脱离数据库独立存在。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class GenerationJobEntity:
    """生成任务领域实体。

    对应原 SQLAlchemy ORM 模型 ``GenerationJob`` 的纯数据表示，
    不含任何 session、lazy-loading 或 ORM 状态。
    """

    id: str
    job_type: str
    status: str = "pending"
    progress: int = 0
    message: str = ""
    result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    dead_letter: bool = False
    celery_task_id: Optional[str] = None
    parent_batch_id: Optional[str] = None

    def mark_cancelled(self, completed_at: Optional[datetime] = None) -> None:
        """标记任务为已取消。"""
        self.status = "cancelled"
        if completed_at is not None:
            self.completed_at = completed_at

    def update_result(self, data: Dict[str, Any]) -> None:
        """更新任务结果（浅合并）。"""
        self.result = {**self.result, **data}

"""
GenerationJob ORM ↔ Entity Mapper
==================================

职责：
  1. 将 SQLAlchemy ORM 实例转换为纯领域实体（隔离 ORM）。
  2. 将领域实体转换回 ORM 实例（用于持久化）。
  3. 将实体状态同步到已有 ORM 实例（避免重复创建）。

设计原则：
  - mapper 不持有 session，无状态。
  - mapper 不访问数据库，仅做字段映射。
"""

from __future__ import annotations

from typing import Any

from vcw_copywriter.db.models import GenerationJob
from domains.generation.domain.entities import GenerationJobEntity


class GenerationJobMapper:
    """GenerationJob ORM 与领域实体之间的双向映射器。"""

    @staticmethod
    def to_entity(orm: Any) -> GenerationJobEntity:
        """将 ORM 实例转换为领域实体。

        Args:
            orm: SQLAlchemy GenerationJob 实例。

        Returns:
            GenerationJobEntity: 纯数据领域实体。
        """
        return GenerationJobEntity(
            id=orm.id,
            job_type=orm.job_type,
            status=orm.status or "pending",
            progress=orm.progress or 0,
            message=orm.message or "",
            result=orm.result or {},
            error=orm.error or "",
            created_at=orm.created_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            retry_count=orm.retry_count or 0,
            max_retries=orm.max_retries or 3,
            dead_letter=bool(orm.dead_letter),
            celery_task_id=orm.celery_task_id,
            parent_batch_id=orm.parent_batch_id,
        )

    @staticmethod
    def to_orm(entity: GenerationJobEntity) -> GenerationJob:
        """将领域实体转换为 ORM 实例（用于新增）。

        Args:
            entity: 纯数据领域实体。

        Returns:
            GenerationJob: SQLAlchemy ORM 实例（未附加到 session）。
        """
        return GenerationJob(
            id=entity.id,
            job_type=entity.job_type,
            status=entity.status,
            progress=entity.progress,
            message=entity.message,
            result=entity.result,
            error=entity.error,
            created_at=entity.created_at,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            retry_count=entity.retry_count,
            max_retries=entity.max_retries,
            dead_letter=entity.dead_letter,
            celery_task_id=entity.celery_task_id,
            parent_batch_id=entity.parent_batch_id,
        )

    @staticmethod
    def update_orm(entity: GenerationJobEntity, orm: GenerationJob) -> None:
        """将领域实体状态同步到已有 ORM 实例（用于更新）。

        Args:
            entity: 包含最新状态的领域实体。
            orm: 已附加到 session 的现有 ORM 实例。
        """
        orm.status = entity.status  # type: ignore[assignment]
        orm.progress = entity.progress  # type: ignore[assignment]
        orm.message = entity.message  # type: ignore[assignment]
        orm.result = entity.result  # type: ignore[assignment]
        orm.error = entity.error  # type: ignore[assignment]
        orm.started_at = entity.started_at  # type: ignore[assignment]
        orm.completed_at = entity.completed_at  # type: ignore[assignment]
        orm.retry_count = entity.retry_count  # type: ignore[assignment]
        orm.dead_letter = entity.dead_letter  # type: ignore[assignment]
        orm.celery_task_id = entity.celery_task_id  # type: ignore[assignment]
        orm.parent_batch_id = entity.parent_batch_id  # type: ignore[assignment]
        # id / job_type / created_at / max_retries 通常不变，不覆盖

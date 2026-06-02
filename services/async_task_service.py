"""
异步任务服务层
==============

隔离 Celery 依赖，负责异步文案生成任务的提交、状态查询与取消。

职责边界：
  - 所有涉及 Celery 的调用均封装在此服务内。
  - GenerationService 不再直接导入 celery。
  - 本服务内部操作 GenerationJobEntity（纯领域实体），
    通过 GenerationJobMapper 在边界处完成 ORM 转换，
    杜绝 ORM 对象向业务逻辑的泄漏。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from app.core.datetime_utils import utc_now
from typing import Dict, Optional

from services.generation_service import GenerationError
from services.base.permission_manager import PermissionDenied

from domains.generation.application.dto import AsyncBatchSubmitDto, AsyncTaskSubmitDto
from domains.generation.domain.entities import GenerationJobEntity
from domains.generation.infrastructure.generation_mapper import GenerationJobMapper


class AsyncTaskError(GenerationError):
    """异步任务服务异常。

    继承 GenerationError，保持路由层异常契约兼容。
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
    ):
        super().__init__(message, code=code)


@dataclass
class TaskStatusDto:
    """异步任务状态 DTO。"""

    id: str = ""
    type: str = "generate"
    status: str = "pending"
    progress: int = 0
    message: str = ""
    result: Dict = field(default_factory=dict)
    error: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AsyncTaskService:
    """异步任务服务。

    封装 Celery 调用与 GenerationJob 持久化，
    使 GenerationService 保持同步生成编排的单一职责。
    """

    def __init__(self, permission_manager=None) -> None:
        self._permission_manager = permission_manager

    def _require_permission(self, action: str) -> None:
        if self._permission_manager is not None:
            try:
                self._permission_manager.check(action)
            except PermissionDenied as exc:
                raise AsyncTaskError(exc.message, code=exc.code) from exc

    # ------------------------------------------------------------------
    # 单任务
    # ------------------------------------------------------------------

    def submit_async_generate(self, dto: AsyncTaskSubmitDto) -> str:
        """提交异步文案生成任务。"""
        topic = dto.req_data.get("topic", "").strip()
        if not topic:
            raise AsyncTaskError("主题不能为空", code="MISSING_TOPIC")

        self._require_permission("generate")

        from vcw_celery_tasks.tasks import generate_copy_task
        from vcw_copywriter.db.session import get_session
        import uuid

        result = generate_copy_task.delay(dto.req_data)
        task_id = result.id

        entity = GenerationJobEntity(
            id=str(uuid.uuid4())[:12],
            job_type="generate",
            status="pending",
            progress=0,
            message="等待执行...",
            celery_task_id=task_id,
            created_at=utc_now(),
        )

        session = get_session()
        try:
            orm = GenerationJobMapper.to_orm(entity)
            session.add(orm)
            session.commit()
        finally:
            session.close()

        return task_id

    def get_async_status(self, task_id: str) -> TaskStatusDto:
        """查询异步任务状态。"""
        from celery.result import AsyncResult
        from celery_app import app as celery_app
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob as GenerationJobOrm

        session = get_session()
        try:
            orm = (
                session.query(GenerationJobOrm)
                .filter(GenerationJobOrm.celery_task_id == task_id)
                .first()
            )
        finally:
            session.close()

        if not orm:
            raise AsyncTaskError("任务不存在", code="TASK_NOT_FOUND")

        # 验证任务存在（通过领域实体转换）
        _ = GenerationJobMapper.to_entity(orm)

        result = AsyncResult(task_id, app=celery_app)

        _STATE_MAP = {
            "PENDING": "pending",
            "STARTED": "running",
            "PROGRESS": "running",
            "RETRY": "pending",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "REVOKED": "cancelled",
        }

        state = result.state
        status = _STATE_MAP.get(state, "pending")

        progress = 0
        message = ""
        result_data = {}
        error = ""

        if state == "PROGRESS" and isinstance(result.info, dict):
            progress = result.info.get("progress", 0)
            message = result.info.get("message", "")
        elif state == "SUCCESS":
            progress = 100
            message = "生成完成"
            result_data = result.result if isinstance(result.result, dict) else {}
        elif state == "FAILURE":
            message = "生成失败"
            error = str(result.result) if result.result else ""
        elif state == "REVOKED":
            message = "任务已取消"
        elif state == "STARTED":
            message = "正在生成..."
            progress = 10
        elif state == "RETRY":
            message = "任务正在重试..."
        else:
            message = "等待执行..."

        completed_at = ""
        if result.date_done:
            completed_at = result.date_done.strftime("%Y-%m-%d %H:%M:%S")

        return TaskStatusDto(
            id=task_id,
            type="generate",
            status=status,
            progress=progress,
            message=message,
            result=result_data,
            error=error,
            created_at="",
            started_at="",
            completed_at=completed_at,
        )

    def cancel_async_task(self, task_id: str) -> bool:
        """取消异步任务。"""
        from celery_app import app as celery_app

        celery_app.control.revoke(task_id, terminate=True)
        return True

    # ------------------------------------------------------------------
    # 批量任务
    # ------------------------------------------------------------------

    def submit_async_batch(self, dto: AsyncBatchSubmitDto) -> str:
        """提交异步批量文案生成任务。"""
        topic = dto.req_data.get("topic", "").strip()
        if not topic:
            raise AsyncTaskError("主题不能为空", code="MISSING_TOPIC")
        if not dto.angles:
            raise AsyncTaskError("角度列表不能为空", code="MISSING_ANGLES")

        self._require_permission("generate_batch")

        from vcw_celery_tasks.tasks import generate_batch_task
        from vcw_copywriter.db.session import get_session
        import uuid

        batch_id = str(uuid.uuid4())[:12]

        entity = GenerationJobEntity(
            id=batch_id,
            job_type="batch",
            status="pending",
            progress=0,
            message=f"等待执行... 共 {len(dto.angles)} 个角度",
            result={
                "total": len(dto.angles),
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            },
            created_at=utc_now(),
        )

        session = get_session()
        try:
            orm = GenerationJobMapper.to_orm(entity)
            session.add(orm)
            session.commit()
        finally:
            session.close()

        generate_batch_task.delay(dto.req_data, dto.angles, batch_id=batch_id)
        return batch_id

    def get_async_batch_status(self, batch_id: str) -> Dict:
        """查询异步批量任务状态。"""
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob as GenerationJobOrm

        session = get_session()
        try:
            parent_orm = (
                session.query(GenerationJobOrm)
                .filter(
                    GenerationJobOrm.id == batch_id,
                    GenerationJobOrm.job_type == "batch",
                )
                .first()
            )

            if not parent_orm:
                raise AsyncTaskError("批次不存在", code="BATCH_NOT_FOUND")

            children_orm = (
                session.query(GenerationJobOrm)
                .filter(GenerationJobOrm.parent_batch_id == batch_id)
                .all()
            )
        finally:
            session.close()

        # 转换为领域实体进行业务逻辑处理
        parent = GenerationJobMapper.to_entity(parent_orm)
        children = [GenerationJobMapper.to_entity(c) for c in children_orm]

        total = len(children)
        completed = sum(1 for c in children if c.status == "completed")
        failed = sum(1 for c in children if c.status == "failed")
        cancelled = sum(1 for c in children if c.status == "cancelled")
        pending = total - completed - failed - cancelled

        status = parent.status
        if status not in ("completed", "failed", "cancelled", "partial"):
            if pending == total:
                status = "pending"
            elif pending > 0:
                status = "running"
            else:
                if failed == 0 and cancelled == 0:
                    status = "completed"
                elif completed > 0:
                    status = "partial"
                elif cancelled > 0:
                    status = "cancelled"
                else:
                    status = "failed"

        progress = (
            int((completed + failed + cancelled) / total * 100)
            if total > 0
            else 0
        )

        items = []
        for child in children:
            angle = (
                (child.result or {}).get("angle", "")
                if child.result
                else ""
            )
            items.append(
                {
                    "subtask_id": child.id,
                    "angle": angle,
                    "status": child.status,
                    "result": child.result or {},
                    "error": child.error or "",
                }
            )

        def _fmt(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""

        return {
            "batch_id": batch_id,
            "status": status,
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "pending": pending,
            "progress_percent": progress,
            "items": items,
            "created_at": _fmt(parent.created_at),
            "started_at": _fmt(parent.started_at),
            "completed_at": _fmt(parent.completed_at),
            "message": (
                f"{completed}/{total} 完成, {failed} 失败, "
                f"{cancelled} 取消, {pending} 等待中"
            ),
        }

    def cancel_async_batch(self, batch_id: str) -> bool:
        """取消异步批量任务及其子任务。"""
        from celery_app import app as celery_app
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob as GenerationJobOrm

        session = get_session()
        try:
            parent_orm = (
                session.query(GenerationJobOrm)
                .filter(
                    GenerationJobOrm.id == batch_id,
                    GenerationJobOrm.job_type == "batch",
                )
                .first()
            )

            if not parent_orm:
                raise AsyncTaskError("批次不存在", code="BATCH_NOT_FOUND")

            children_orm = (
                session.query(GenerationJobOrm)
                .filter(GenerationJobOrm.parent_batch_id == batch_id)
                .all()
            )

            # 业务逻辑在领域实体上执行
            for child_orm in children_orm:
                child_entity = GenerationJobMapper.to_entity(child_orm)
                if child_entity.status in ("pending", "running"):
                    if child_entity.celery_task_id:
                        celery_app.control.revoke(
                            child_entity.celery_task_id, terminate=True
                        )
                    child_entity.mark_cancelled()
                    GenerationJobMapper.update_orm(child_entity, child_orm)

            parent_entity = GenerationJobMapper.to_entity(parent_orm)
            parent_entity.mark_cancelled(completed_at=utc_now())
            GenerationJobMapper.update_orm(parent_entity, parent_orm)

            session.commit()
        finally:
            session.close()

        return True

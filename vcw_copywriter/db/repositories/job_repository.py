"""
GenerationJob Repository
生成任务数据访问层（原 task_queue.db 的替代）。
"""
from app.core.datetime_utils import utc_now
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .base import BaseRepository
from ..models import GenerationJob


class JobRepository(BaseRepository):
    """生成任务 Repository"""

    def __init__(self, session: Session):
        super().__init__(session, GenerationJob)

    def submit(self, job_type: str) -> GenerationJob:
        import uuid
        job = GenerationJob(
            id=str(uuid.uuid4())[:12],
            job_type=job_type,
            status="pending",
            progress=0,
            message="等待执行...",
            created_at=utc_now(),
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def update_task(self, job_id: str, **fields) -> bool:
        job = self.get_by_id(job_id)
        if not job:
            return False
        for k, v in fields.items():
            if hasattr(job, k):
                setattr(job, k, v)
        self.session.commit()
        return True

    def cancel(self, job_id: str) -> bool:
        updated = (
            self.session.query(GenerationJob)
            .filter(
                GenerationJob.id == job_id,
                ~GenerationJob.status.in_(["completed", "failed"]),
            )
            .update(
                {
                    "status": "cancelled",
                    "message": "用户已取消",
                },
                synchronize_session=False,
            )
        )
        self.session.commit()
        return updated > 0

    def get_status(self, job_id: str) -> Optional[Dict]:
        job = self.get_by_id(job_id)
        if not job:
            return None
        return job.to_dict()

    def list_tasks(self, limit: int = 20) -> List[Dict]:
        jobs = self.session.query(GenerationJob).order_by(
            desc(GenerationJob.created_at)
        ).limit(limit).all()
        return [j.to_dict() for j in jobs]

    def recover_on_startup(self):
        """启动时恢复：将 pending/running 任务批量标记为 failed"""
        from sqlalchemy import func

        updated = (
            self.session.query(GenerationJob)
            .filter(GenerationJob.status.in_(["pending", "running"]))
            .update(
                {
                    "status": "failed",
                    "message": "服务重启导致任务中断",
                    "completed_at": func.now(),
                },
                synchronize_session=False,
            )
        )
        self.session.commit()
        if updated:
            print(f"[JobRepository] 恢复 {updated} 个未完成任务为 failed")

    def cleanup_old_tasks(self):
        """清理旧任务，只保留最近 100 个已完成任务"""
        # 获取需要保留的 100 个最新 completed/failed/cancelled 任务的 ID
        subq = self.session.query(GenerationJob.id).filter(
            GenerationJob.status.in_(["completed", "failed", "cancelled"])
        ).order_by(desc(GenerationJob.completed_at)).limit(100).subquery()

        # 删除不在 subq 中的 completed/failed/cancelled 任务
        deleted = self.session.query(GenerationJob).filter(
            GenerationJob.status.in_(["completed", "failed", "cancelled"]),
            ~GenerationJob.id.in_(subq)
        ).delete(synchronize_session=False)
        self.session.commit()
        return deleted

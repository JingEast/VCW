"""VCW Celery 任务定义。

当前仅注册示例任务，不迁移旧任务（vcw_copywriter.task_queue 保持独立）。
未来可在此注册：
  - 异步文案生成
  - 批量热点爬取
  - 定时报告生成
"""

from __future__ import annotations

import uuid
from datetime import datetime

from celery_app import app


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def echo_task(self, message: str) -> str:
    """示例任务：返回输入消息。"""
    return f"Echo: {message}"


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_copy_task(self, req_data: dict) -> dict:
    """异步文案生成任务。

    调用 GenerationService._generate_copy_internal 完成生成，
    支持进度上报、失败重试以及死信队列。
    作为批量子任务时，自动更新父批次进度。
    """
    from app.core.container import get_service
    from services.generation_service import GenerationError

    svc = get_service("generation_service")

    batch_id = req_data.get("_batch_id")
    angle = req_data.get("angle", "")
    task_id = self.request.id

    # 更新子任务状态为 running（仅在 DB 中有记录时）
    if batch_id:
        _update_job_status(task_id, status="running", started_at=datetime.utcnow())

    def on_progress(progress: int, message: str):
        self.update_state(state="PROGRESS", meta={"progress": progress, "message": message})

    try:
        result = svc._generate_copy_internal(req_data, on_progress=on_progress)
        if batch_id:
            result["angle"] = angle
            _update_batch_progress(batch_id, task_id, "success", result)
        return result
    except GenerationError as exc:
        try:
            self.retry(exc=exc)
        except Exception:
            if batch_id:
                _update_batch_progress(
                    batch_id, task_id, "failed",
                    {"error": str(exc), "angle": angle}
                )
            _store_dead_letter(req_data, str(exc), task_id)
            raise
    except Exception as exc:
        try:
            self.retry(exc=exc)
        except Exception:
            if batch_id:
                _update_batch_progress(
                    batch_id, task_id, "failed",
                    {"error": str(exc), "angle": angle}
                )
            _store_dead_letter(req_data, str(exc), task_id)
            raise


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_batch_task(self, req_data: dict, angles: list, batch_id: str) -> dict:
    """异步批量文案生成任务。

    为每个角度创建子任务记录并提交 Celery group 并行执行。
    """
    from celery import group

    # 更新父批次为 running
    _update_job_status(batch_id, status="running", started_at=datetime.utcnow())

    subtasks = []
    for angle in angles:
        sub_id = str(uuid.uuid4())[:12]
        sub_req = {**req_data, "angle": angle, "_batch_id": batch_id}

        # 预创建子任务 DB 记录
        _create_job(
            id=sub_id,
            job_type="generate",
            status="pending",
            parent_batch_id=batch_id,
            celery_task_id=sub_id,
            result={"angle": angle},
        )

        sig = generate_copy_task.s(sub_req).set(task_id=sub_id)
        subtasks.append(sig)

    if subtasks:
        group(subtasks).apply_async()

    return {"batch_id": batch_id, "total": len(angles), "status": "submitted"}


@app.task(bind=True)
def dead_letter_task(self) -> dict:
    """死信队列处理任务。

    扫描并处理标记为 dead_letter 的 GenerationJob 记录。
    """
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    session = get_session()
    try:
        jobs = session.query(GenerationJob).filter(
            GenerationJob.dead_letter.is_(True),
            GenerationJob.status == "failed",
        ).all()

        processed = 0
        for job in jobs:
            # 目前仅记录日志，未来可扩展为人工审核/重新投递
            processed += 1

        return {"processed": processed, "dead_letter_jobs": [j.id for j in jobs]}
    finally:
        session.close()


@app.task(bind=True)
def health_check_task(self) -> dict:
    """健康检查任务。"""
    from celery_app import health_check
    return health_check()


# ------------------------------------------------------------------------------
# 内部辅助函数
# ------------------------------------------------------------------------------

def _create_job(**kwargs) -> None:
    """创建 GenerationJob 记录。"""
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    session = get_session()
    try:
        job = GenerationJob(**kwargs)
        session.add(job)
        session.commit()
    finally:
        session.close()


def _update_job_status(job_id: str, **kwargs) -> None:
    """更新 GenerationJob 状态。"""
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    session = get_session()
    try:
        job = session.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            session.commit()
    finally:
        session.close()


def _update_batch_progress(batch_id: str, subtask_id: str, status: str, data: dict) -> None:
    """更新批次子任务进度并重新计算父批次聚合状态。

    使用行锁防止并发更新竞争（PostgreSQL 下生效，SQLite 下被 SQLAlchemy 静默忽略）。
    """
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    session = get_session()
    try:
        parent = (
            session.query(GenerationJob)
            .filter(GenerationJob.id == batch_id)
            .with_for_update()
            .first()
        )
        if not parent:
            return

        # 更新子任务
        child = (
            session.query(GenerationJob)
            .filter(GenerationJob.id == subtask_id)
            .first()
        )
        if child:
            child.status = status
            if status == "success":
                child.result = data
            elif status == "failed":
                child.error = str(data.get("error", ""))[:500]
            child.completed_at = datetime.utcnow()

        # 重新聚合
        children = (
            session.query(GenerationJob)
            .filter(GenerationJob.parent_batch_id == batch_id)
            .all()
        )
        total = len(children)
        if total == 0:
            return

        completed = sum(1 for c in children if c.status == "completed")
        failed = sum(1 for c in children if c.status == "failed")
        cancelled = sum(1 for c in children if c.status == "cancelled")
        done = completed + failed + cancelled

        parent.result = {
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
        }
        parent.progress = int(done / total * 100)

        if done == total:
            parent.completed_at = datetime.utcnow()
            if failed == 0 and cancelled == 0:
                parent.status = "completed"
                parent.message = f"全部 {total} 个任务完成"
            elif completed > 0:
                parent.status = "partial"
                parent.message = f"{completed}/{total} 完成, {failed} 失败, {cancelled} 取消"
            elif cancelled > 0:
                parent.status = "cancelled"
                parent.message = f"全部 {total} 个任务已取消"
            else:
                parent.status = "failed"
                parent.message = f"全部 {total} 个任务失败"
        else:
            pending = total - done
            parent.message = f"{completed}/{total} 完成, {failed} 失败, {cancelled} 取消, {pending} 等待中"

        session.commit()
    finally:
        session.close()


def _store_dead_letter(req_data: dict, error: str, celery_task_id: str) -> None:
    """将失败任务写入死信队列（GenerationJob）。"""
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    session = get_session()
    try:
        job = GenerationJob(
            id=str(uuid.uuid4())[:12],
            job_type="generate",
            status="failed",
            error=error[:500],
            dead_letter=True,
            celery_task_id=celery_task_id,
            created_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

"""VCW Celery 任务定义。

当前仅注册示例任务，不迁移旧任务（vcw_copywriter.task_queue 保持独立）。
未来可在此注册：
  - 异步文案生成
  - 批量热点爬取
  - 定时报告生成
"""

from __future__ import annotations

import hashlib
import uuid
from app.core.datetime_utils import utc_now

from celery_app import app


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def echo_task(self, message: str) -> str:
    """示例任务：返回输入消息。"""
    return f"Echo: {message}"


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_copy_task(self, req_data: dict) -> dict:  # type: ignore[return]
    """异步文案生成任务。

    调用 GenerationService._generate_copy_internal 完成生成，
    支持进度上报、失败重试以及死信队列。
    作为批量子任务时，自动更新父批次进度。
    """
    from interfaces.service_provider import get_service
    from services.generation_service import GenerationError

    svc = get_service("generation_service")

    batch_id = req_data.get("_batch_id")
    angle = req_data.get("angle", "")
    task_id = self.request.id
    # 优先继承父批次传递的 trace_id，否则从 task request 生成
    trace_id = req_data.get("_trace_id") or _get_task_trace_id(self)

    # 更新子任务状态为 running（仅在 DB 中有记录时）
    if batch_id:
        _update_job_status(task_id, status="running", started_at=utc_now())

    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        "[trace_id=%s] generate_copy_task start | task_id=%s batch_id=%s angle=%s", trace_id, task_id, batch_id, angle
    )

    _record_celery_metric("generate_copy_task", "started")

    def on_progress(progress: int, message: str):
        self.update_state(state="PROGRESS", meta={"progress": progress, "message": message})

    try:
        result = svc._generate_copy_internal(req_data, on_progress=on_progress)
        if batch_id:
            result["angle"] = angle
            _update_batch_progress(batch_id, task_id, "success", result)
        logger.info("[trace_id=%s] generate_copy_task success | task_id=%s", trace_id, task_id)
        _record_celery_metric("generate_copy_task", "success")
        return result
    except GenerationError as exc:
        try:
            self.retry(exc=exc)
        except Exception:
            logger.error("[trace_id=%s] generate_copy_task failed | task_id=%s error=%s", trace_id, task_id, exc)
            _record_celery_metric("generate_copy_task", "failed")
            if batch_id:
                _update_batch_progress(batch_id, task_id, "failed", {"error": str(exc), "angle": angle})
            _store_dead_letter(req_data, str(exc), task_id, trace_id)
            raise
    except Exception as exc:
        try:
            self.retry(exc=exc)
        except Exception:
            logger.error("[trace_id=%s] generate_copy_task failed | task_id=%s error=%s", trace_id, task_id, exc)
            _record_celery_metric("generate_copy_task", "failed")
            if batch_id:
                _update_batch_progress(batch_id, task_id, "failed", {"error": str(exc), "angle": angle})
            _store_dead_letter(req_data, str(exc), task_id, trace_id)
            raise


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_batch_task(self, req_data: dict, angles: list, batch_id: str) -> dict:
    """异步批量文案生成任务。

    为每个角度创建子任务记录并提交 Celery group 并行执行。
    """
    from celery import group

    trace_id = _get_task_trace_id(self)

    import logging

    logger = logging.getLogger(__name__)
    logger.info("[trace_id=%s] generate_batch_task start | batch_id=%s angles=%d", trace_id, batch_id, len(angles))
    _record_celery_metric("generate_batch_task", "started")

    # 更新父批次为 running
    _update_job_status(batch_id, status="running", started_at=utc_now())

    subtasks = []
    for angle in angles:
        # 使用确定性 ID（batch_id + angle hash）保证幂等性：
        # 同一批次的同一角度始终生成相同子任务 ID，避免重复创建。
        sub_id = _make_subtask_id(batch_id, angle)
        # 将父批次 trace_id 传递给子任务，实现分布式追踪上下文传递
        sub_req = {**req_data, "angle": angle, "_batch_id": batch_id, "_trace_id": trace_id}

        # 预创建子任务 DB 记录（若已存在则跳过，保证幂等）
        _create_job_if_not_exists(
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
        job_ids = (
            session.query(GenerationJob.id)
            .filter(
                GenerationJob.dead_letter.is_(True),
                GenerationJob.status == "failed",
            )
            .all()
        )
        job_ids = [j.id for j in job_ids]
        return {"processed": len(job_ids), "dead_letter_jobs": job_ids}
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


def _get_task_trace_id(task) -> str:
    """从 Celery task request 中提取 trace_id；不存在时生成新的。"""
    req = getattr(task, "request", None)
    if req is None:
        return uuid.uuid4().hex[:12]
    meta = getattr(req, "meta", {}) or {}
    trace_id = meta.get("trace_id")
    if trace_id is not None:
        return str(trace_id)
    # 兼容直接设置在 request 上的属性
    trace_id = getattr(req, "trace_id", None)
    if trace_id is not None:
        return str(trace_id)
    return uuid.uuid4().hex[:12]


def _record_celery_metric(task_name: str, status: str) -> None:
    """记录 Celery 任务指标到全局收集器。"""
    from app.core.metrics import get_global_collector

    try:
        collector = get_global_collector()
        collector.record_celery_task(task_name, status)
    except Exception:
        # 指标记录不应影响任务执行
        pass


def _make_subtask_id(batch_id: str, angle: str) -> str:
    """生成确定性子任务 ID（batch_id + angle 的哈希），保证幂等性。"""
    raw = f"{batch_id}:{angle}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _create_job_if_not_exists(**kwargs) -> None:
    """创建 GenerationJob 记录（若 ID 已存在则跳过，保证幂等）。"""
    from vcw_copywriter.db.session import get_session
    from vcw_copywriter.db.models import GenerationJob

    job_id = kwargs.get("id")
    session = get_session()
    try:
        existing = session.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if existing is not None:
            return
        job = GenerationJob(**kwargs)
        session.add(job)
        session.commit()
    finally:
        session.close()


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
        parent = session.query(GenerationJob).filter(GenerationJob.id == batch_id).with_for_update().first()
        if not parent:
            return

        # 更新子任务
        child = session.query(GenerationJob).filter(GenerationJob.id == subtask_id).first()
        if child:
            child.status = status
            if status == "success":
                child.result = data
            elif status == "failed":
                child.error = str(data.get("error", ""))[:500]
            child.completed_at = utc_now()

        # 重新聚合（使用 COUNT 聚合查询，避免加载所有子任务对象）
        from sqlalchemy import func

        total = session.query(func.count(GenerationJob.id)).filter(GenerationJob.parent_batch_id == batch_id).scalar()
        if total == 0:
            return

        completed = (
            session.query(func.count(GenerationJob.id))
            .filter(GenerationJob.parent_batch_id == batch_id, GenerationJob.status == "completed")
            .scalar()
        )
        failed = (
            session.query(func.count(GenerationJob.id))
            .filter(GenerationJob.parent_batch_id == batch_id, GenerationJob.status == "failed")
            .scalar()
        )
        cancelled = (
            session.query(func.count(GenerationJob.id))
            .filter(GenerationJob.parent_batch_id == batch_id, GenerationJob.status == "cancelled")
            .scalar()
        )
        done = completed + failed + cancelled

        parent.result = {
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
        }
        parent.progress = int(done / total * 100)

        if done == total:
            parent.completed_at = utc_now()
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


def _store_dead_letter(req_data: dict, error: str, celery_task_id: str, trace_id: str = "-") -> None:
    """将失败任务写入死信队列（GenerationJob），附带 trace_id 用于错误关联。"""
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
            result={"trace_id": trace_id, "req_data": req_data},
            created_at=utc_now(),
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

"""
异步任务队列模块 v3.0 — PostgreSQL 专用适配器

完全基于 SQLAlchemy ORM + JobRepository，不再支持 SQLite 回退。
任务数据统一存储在 PostgreSQL 的 generation_jobs 表中。
"""

import json
import threading
from app.core.datetime_utils import utc_now
from typing import Dict, Callable, Optional

from .db.session import init_db, get_session
from .db.repositories.job_repository import JobRepository


class TaskQueue:
    """任务队列 — PostgreSQL Repository 适配器"""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = True
        self._current_task_id: Optional[str] = None
        init_db()
        self._recover_on_startup()

    def _repo_call(self, method: str, *args, **kwargs):
        """线程安全地执行 Repository 方法（每次新建独立 session）。"""
        session = get_session()
        repo = JobRepository(session)
        try:
            return getattr(repo, method)(*args, **kwargs)
        finally:
            session.close()

    def _recover_on_startup(self):
        """启动时恢复：将 pending/running 任务标记为 failed"""
        self._repo_call("recover_on_startup")

    def submit(self, task_type: str, worker_fn: Callable, **kwargs) -> str:
        job = self._repo_call("submit", task_type)
        task_id = job.id

        t = threading.Thread(
            target=self._run_task,
            args=(task_id, worker_fn),
            kwargs=kwargs,
            daemon=True,
        )
        t.start()
        return task_id

    def _update_task(self, task_id: str, **fields):
        if not fields:
            return
        self._repo_call("update_task", task_id, **fields)

    def _run_task(self, task_id: str, worker_fn: Callable, **kwargs):
        self._update_task(task_id, status="running", started_at=utc_now())
        self._current_task_id = task_id
        try:
            def update_progress(progress: int, message: str):
                self._update_task(task_id, progress=progress, message=message)

            result = worker_fn(
                task=type("Task", (), {
                    "id": task_id,
                    "update_progress": update_progress,
                })(),
                **kwargs,
            )

            # 检查是否被取消
            job = self._repo_call("get_by_id", task_id)
            if job and job.status == "cancelled":
                return

            result_json = (
                json.dumps(result)
                if isinstance(result, dict)
                else json.dumps({"output": str(result)})
            )
            self._update_task(
                task_id,
                status="completed",
                progress=100,
                message="生成完成",
                result=result_json,
                completed_at=utc_now(),
            )
        except Exception as e:
            job = self._repo_call("get_by_id", task_id)
            if job and job.status != "cancelled":
                self._update_task(
                    task_id,
                    status="failed",
                    error=str(e)[:500],
                    completed_at=utc_now(),
                )
        finally:
            if self._current_task_id == task_id:
                self._current_task_id = None
            self._cleanup_old_tasks()

    def cancel(self, task_id: str) -> bool:
        return self._repo_call("cancel", task_id)

    def get_status(self, task_id: str) -> Optional[Dict]:
        return self._repo_call("get_status", task_id)

    def list_tasks(self, limit: int = 20) -> list:
        return self._repo_call("list_tasks", limit)

    def _cleanup_old_tasks(self):
        self._repo_call("cleanup_old_tasks")


_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue

"""VCW Celery 应用配置。

最小可运行配置：
  - Broker: Redis
  - Result Backend: PostgreSQL
  - 不迁移旧任务（vcw_copywriter.task_queue 保持独立）
  - 仅注册新任务。

使用示例：
    from celery_app import app
    @app.task(bind=True)
    def my_task(self, x, y):
        return x + y
"""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init

# ------------------------------------------------------------------------------
# 环境变量配置（可通过 .env 或 shell 覆盖）
# ------------------------------------------------------------------------------
_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "db+postgresql+psycopg2://vcw:vcw@localhost:5432/vcw_celery",
)

# ------------------------------------------------------------------------------
# Celery App 实例
# ------------------------------------------------------------------------------
app = Celery(
    "vcw",
    broker=_BROKER_URL,
    backend=_RESULT_BACKEND,
    include=["vcw_celery_tasks.tasks"],  # 任务模块（未来扩展）
)

# ------------------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------------------
app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务行为
    task_track_started=True,
    task_time_limit=3600,          # 单任务硬时限 1 小时
    task_soft_time_limit=3300,     # 软时限 55 分钟（可捕获异常）
    worker_prefetch_multiplier=1,  # 公平调度，避免 worker 饥饿
    worker_max_tasks_per_child=1000,  # 防止内存泄漏

    # Result Backend
    result_expires=86400,          # 结果保留 24 小时
    result_extended=True,          # 保存更多元数据

    # Broker 连接池
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)


@worker_process_init.connect
def init_container(**kwargs):
    """Worker 进程启动时初始化 DI 容器。"""
    from app.core.container import AppContainer, set_container

    container = AppContainer()
    set_container(container)


def health_check() -> dict:
    """返回 Celery 连接健康状态（用于 /health 端点）。"""
    try:
        with app.connection() as conn:
            conn.ensure_connection(max_retries=1)
        return {"status": "ok", "broker": _BROKER_URL, "backend": _RESULT_BACKEND}
    except Exception as exc:
        return {"status": "error", "detail": str(exc), "broker": _BROKER_URL, "backend": _RESULT_BACKEND}


if __name__ == "__main__":
    app.start()

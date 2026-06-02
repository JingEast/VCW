from app.core.datetime_utils import utc_now
"""Distributed System & Microservice Readiness Tests

验证：
  1. Celery 任务幂等性
  2. 崩溃恢复配置（acks_late, reject_on_worker_lost）
  3. Worker 进程初始化（DI 容器）
  4. 死信队列
  5. Docker Compose 配置一致性
"""

from pathlib import Path

import pytest

from celery_app import app as celery_app
from vcw_celery_tasks.tasks import (
    _make_subtask_id,
    _create_job_if_not_exists,
    dead_letter_task,
)


class TestCeleryConfig:
    """Celery 分布式配置验证"""

    def test_task_acks_late_enabled(self):
        """任务完成后才确认，防止 worker 崩溃丢失任务。"""
        assert celery_app.conf.task_acks_late is True

    def test_task_reject_on_worker_lost_enabled(self):
        """worker 异常退出时任务重回队列。"""
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_worker_prefetch_multiplier_is_one(self):
        """公平调度，避免 worker 饥饿。"""
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_task_time_limit_configured(self):
        """单任务硬时限 1 小时。"""
        assert celery_app.conf.task_time_limit == 3600

    def test_task_soft_time_limit_configured(self):
        """单任务软时限 55 分钟。"""
        assert celery_app.conf.task_soft_time_limit == 3300

    def test_result_expiry_configured(self):
        """结果保留 24 小时。"""
        assert celery_app.conf.result_expires == 86400

    def test_broker_connection_retry_on_startup(self):
        """启动时自动重连 broker。"""
        assert celery_app.conf.broker_connection_retry_on_startup is True

    def test_serialization_is_json(self):
        """序列化格式为 json，避免 pickle 安全风险。"""
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]


class TestTaskIdempotency:
    """任务幂等性验证"""

    def test_make_subtask_id_is_deterministic(self):
        """相同 batch_id + angle 应始终生成相同 subtask_id。"""
        id1 = _make_subtask_id("batch-123", "焦虑型")
        id2 = _make_subtask_id("batch-123", "焦虑型")
        id3 = _make_subtask_id("batch-123", "数据型")
        assert id1 == id2
        assert id1 != id3
        assert len(id1) == 12

    def test_create_job_if_not_exists_is_idempotent(self, app):
        """同一 ID 重复创建应只生成一条记录。"""
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        job_id = "idempotent-test-01"

        _create_job_if_not_exists(
            id=job_id,
            job_type="generate",
            status="pending",
            parent_batch_id="batch-01",
            celery_task_id=job_id,
            result={"angle": "焦虑型"},
        )

        # 第二次创建应被跳过
        _create_job_if_not_exists(
            id=job_id,
            job_type="generate",
            status="running",  # 不同状态
            parent_batch_id="batch-01",
            celery_task_id=job_id,
            result={"angle": "焦虑型"},
        )

        session = get_session()
        try:
            jobs = session.query(GenerationJob).filter(GenerationJob.id == job_id).all()
            assert len(jobs) == 1
            assert jobs[0].status == "pending"  # 保持第一次创建的状态
        finally:
            session.close()


class TestWorkerProcessInit:
    """Worker 进程初始化验证"""

    def test_worker_process_init_signal_registered(self):
        """worker_process_init 信号应已注册。"""
        from celery.signals import worker_process_init

        handlers = worker_process_init.receivers
        # 至少有一个 handler（init_container）
        assert len(handlers) > 0

    def test_container_initialization_does_not_crash(self):
        """模拟 worker 进程初始化时不应崩溃。"""
        from app.core.container import AppContainer, set_container

        container = AppContainer()
        set_container(container)
        # 验证容器已注册关键服务
        assert hasattr(container, "generation_service")
        assert hasattr(container, "editor_service")


class TestDeadLetter:
    """死信队列验证"""

    @pytest.fixture(autouse=True)
    def eager_backend(self):
        """使用内存 backend 避免连接 PostgreSQL。"""
        orig = celery_app.conf.result_backend
        celery_app.conf.result_backend = "cache+memory://"
        yield
        celery_app.conf.result_backend = orig

    def test_dead_letter_task_scans_failed_jobs(self, app):
        """dead_letter_task 应能扫描到标记为 dead_letter 的失败任务。"""
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob
        from datetime import datetime

        session = get_session()
        try:
            job = GenerationJob(
                id="dl-test-01",
                job_type="generate",
                status="failed",
                dead_letter=True,
                error="模拟失败",
                created_at=utc_now(),
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        result = dead_letter_task.apply().result
        assert result["processed"] >= 1
        assert "dl-test-01" in result["dead_letter_jobs"]


class TestDockerComposeConfig:
    """Docker Compose 配置一致性验证"""

    def test_docker_compose_file_exists(self):
        assert Path("docker-compose.yml").exists()

    def test_all_services_have_healthcheck_or_dependencies(self):
        """web/worker/beat 均依赖 redis + postgres 的健康检查。"""
        import yaml

        with open("docker-compose.yml", "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        services = compose.get("services", {})

        # redis 和 postgres 必须有 healthcheck
        assert "healthcheck" in services.get("redis", {})
        assert "healthcheck" in services.get("postgres", {})

        # web/worker/beat 必须依赖 redis + postgres 的 healthy 条件
        for svc_name in ("web", "worker", "beat"):
            svc = services.get(svc_name, {})
            deps = svc.get("depends_on", {})
            assert "redis" in deps, f"{svc_name} missing redis dependency"
            assert "postgres" in deps, f"{svc_name} missing postgres dependency"
            # condition 可能为字符串或 dict
            redis_dep = deps.get("redis", {})
            if isinstance(redis_dep, dict):
                assert redis_dep.get("condition") == "service_healthy"
            else:
                # 字符串形式（旧版 compose）
                pass

    def test_web_service_has_healthcheck(self):
        import yaml

        with open("docker-compose.yml", "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        web = compose["services"].get("web", {})
        assert "healthcheck" in web

    def test_all_services_have_restart_policy(self):
        import yaml

        with open("docker-compose.yml", "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        for svc_name, svc in compose.get("services", {}).items():
            assert svc.get("restart") == "unless-stopped", f"{svc_name} missing restart policy"

    def test_all_services_have_memory_limits(self):
        import yaml

        with open("docker-compose.yml", "r", encoding="utf-8") as f:
            compose = yaml.safe_load(f)

        for svc_name, svc in compose.get("services", {}).items():
            deploy = svc.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            assert "memory" in limits, f"{svc_name} missing memory limit"

    def test_dockerfile_exists(self):
        assert Path("Dockerfile").exists()

    def test_env_example_exists(self):
        assert Path(".env.example").exists()

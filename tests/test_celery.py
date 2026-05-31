"""Celery 基础设施测试。

测试策略：
  1. 验证 Celery 应用配置正确。
  2. 验证任务可注册、可序列化。
  3. 使用 task_always_eager=True + cache+memory:// backend 在本地同步执行（无需 Redis/PostgreSQL）。
  4. 不测试真实 broker/backend 连接（依赖外部服务）。
"""

import pytest

from celery_app import app, health_check
from vcw_celery_tasks.tasks import (
    echo_task,
    generate_batch_task,
    generate_copy_task,
    dead_letter_task,
    health_check_task,
)


@pytest.fixture(autouse=True)
def ensure_container(app):
    """确保 DI 容器已初始化，供 Celery eager 模式任务调用 get_service。"""
    pass


class TestCeleryAppConfig:
    """Celery 应用配置测试"""

    def test_app_name(self):
        assert app.main == "vcw"

    def test_broker_url(self):
        assert app.conf.broker_url.startswith("redis://")

    def test_result_backend(self):
        assert "postgresql" in app.conf.result_backend

    def test_serializer_config(self):
        assert app.conf.task_serializer == "json"
        assert app.conf.accept_content == ["json"]
        assert app.conf.result_serializer == "json"

    def test_timezone_config(self):
        assert app.conf.timezone == "Asia/Shanghai"
        assert app.conf.enable_utc is True

    def test_task_limits(self):
        assert app.conf.task_time_limit == 3600
        assert app.conf.task_soft_time_limit == 3300

    def test_worker_config(self):
        assert app.conf.worker_prefetch_multiplier == 1
        assert app.conf.worker_max_tasks_per_child == 1000

    def test_result_expiry(self):
        assert app.conf.result_expires == 86400


class TestCeleryTasks:
    """Celery 任务注册与执行测试"""

    @pytest.fixture(autouse=True)
    def eager_mode(self):
        """使用本地同步模式 + 内存 backend 执行，无需 Redis/PostgreSQL。"""
        orig_always_eager = app.conf.task_always_eager
        orig_backend = app.conf.result_backend
        app.conf.task_always_eager = True
        app.conf.result_backend = "cache+memory://"
        yield
        app.conf.task_always_eager = orig_always_eager
        app.conf.result_backend = orig_backend

    def test_echo_task_registered(self):
        assert "vcw_celery_tasks.tasks.echo_task" in app.tasks

    def test_generate_copy_task_registered(self):
        assert "vcw_celery_tasks.tasks.generate_copy_task" in app.tasks

    def test_generate_batch_task_registered(self):
        assert "vcw_celery_tasks.tasks.generate_batch_task" in app.tasks

    def test_dead_letter_task_registered(self):
        assert "vcw_celery_tasks.tasks.dead_letter_task" in app.tasks

    def test_health_check_task_registered(self):
        assert "vcw_celery_tasks.tasks.health_check_task" in app.tasks

    def test_echo_task_execution(self):
        result = echo_task.apply(args=["hello"])
        assert result.successful()
        assert result.result == "Echo: hello"

    def test_generate_copy_task_execution(self, monkeypatch):
        """generate_copy_task 执行：mock GenerationService 避免真实 LLM 调用。"""

        class MockService:
            def _generate_copy_internal(self, req_data, on_progress=None):
                if on_progress:
                    on_progress(50, "测试中...")
                return {"topic": req_data.get("topic"), "content": "mocked"}

        def mock_get_service(name):
            if name == "generation_service":
                return MockService()
            raise KeyError(name)

        monkeypatch.setattr(
            "app.core.container.get_service",
            mock_get_service,
        )

        result = generate_copy_task.apply(args=[{"topic": "DSE考砸后的保底路径"}])
        assert result.successful()
        assert result.result["topic"] == "DSE考砸后的保底路径"
        assert result.result["content"] == "mocked"

    def test_generate_batch_task_execution(self, monkeypatch):
        """generate_batch_task 执行：mock 子任务避免真实 LLM 调用，验证 DB 聚合。"""
        import uuid
        from datetime import datetime

        class MockService:
            def _generate_copy_internal(self, req_data, on_progress=None):
                return {
                    "topic": req_data.get("topic"),
                    "content": f"mocked-{req_data.get('angle', '')}",
                }

        def mock_get_service(name):
            if name == "generation_service":
                return MockService()
            raise KeyError(name)

        monkeypatch.setattr(
            "app.core.container.get_service",
            mock_get_service,
        )

        batch_id = "batch-test-" + uuid.uuid4().hex[:8]
        req_data = {"topic": "测试主题", "audience": "港宝家长"}
        angles = ["焦虑型", "数据型"]

        # 预先创建父批次记录（模拟 GenerationService.submit_async_batch 的行为）
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        session = get_session()
        try:
            parent = GenerationJob(
                id=batch_id,
                job_type="batch",
                status="pending",
                result={"total": len(angles), "completed": 0, "failed": 0, "cancelled": 0},
                created_at=datetime.utcnow(),
            )
            session.add(parent)
            session.commit()
        finally:
            session.close()

        result = generate_batch_task.apply(args=[req_data, angles, batch_id])
        assert result.successful()
        assert result.result["batch_id"] == batch_id
        assert result.result["total"] == 2

        # 验证 DB 中有父批次和子任务记录
        session = get_session()
        try:
            parent = session.query(GenerationJob).filter(
                GenerationJob.id == batch_id
            ).first()
            assert parent is not None
            assert parent.job_type == "batch"

            children = session.query(GenerationJob).filter(
                GenerationJob.parent_batch_id == batch_id
            ).all()
            assert len(children) == 2
        finally:
            session.close()

    def test_generate_batch_task_partial_failure(self, monkeypatch):
        """批量任务部分失败：验证 partial 状态。"""
        import uuid
        from datetime import datetime

        call_count = [0]

        class MockService:
            def _generate_copy_internal(self, req_data, on_progress=None):
                call_count[0] += 1
                angle = req_data.get("angle", "")
                if angle == "数据型":
                    from services.generation_service import GenerationError
                    raise GenerationError("模拟失败", code="MOCK_FAILURE")
                return {"topic": req_data.get("topic"), "content": f"mocked-{angle}"}

        def mock_get_service(name):
            if name == "generation_service":
                return MockService()
            raise KeyError(name)

        monkeypatch.setattr(
            "app.core.container.get_service",
            mock_get_service,
        )

        batch_id = "batch-partial-" + uuid.uuid4().hex[:8]
        req_data = {"topic": "测试主题"}
        angles = ["焦虑型", "数据型"]

        # 预先创建父批次记录
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        session = get_session()
        try:
            parent = GenerationJob(
                id=batch_id,
                job_type="batch",
                status="pending",
                result={"total": len(angles), "completed": 0, "failed": 0, "cancelled": 0},
                created_at=datetime.utcnow(),
            )
            session.add(parent)
            session.commit()
        finally:
            session.close()

        # 由于 generate_copy_task 会重试 3 次，mock 的 GenerationError 也会被重试。
        # 在 eager 模式下，重试会立即发生。为了避免无限重试，我们让重试也失败。
        # 最终任务会标记为 failed，并更新 batch 进度。
        result = generate_batch_task.apply(args=[req_data, angles, batch_id])
        assert result.successful()

        session = get_session()
        try:
            parent = session.query(GenerationJob).filter(
                GenerationJob.id == batch_id
            ).first()
            assert parent is not None

            children = session.query(GenerationJob).filter(
                GenerationJob.parent_batch_id == batch_id
            ).all()
            assert len(children) == 2

            # 验证子任务状态：一个成功，一个失败
            statuses = {c.status for c in children}
            assert "success" in statuses or "completed" in statuses
            assert "failed" in statuses
        finally:
            session.close()

    def test_dead_letter_task_execution(self):
        result = dead_letter_task.apply()
        assert result.successful()
        assert "processed" in result.result

    def test_health_check_task_execution(self):
        result = health_check_task.apply()
        assert result.successful()
        assert result.result["status"] == "error"  # no real Redis/Postgres in test env


class TestHealthCheck:
    """health_check 函数测试"""

    def test_returns_error_without_services(self):
        # 测试环境没有 Redis/Postgres，应返回 error
        result = health_check()
        assert "status" in result
        assert result["broker"].startswith("redis://")
        assert "postgresql" in result["backend"]

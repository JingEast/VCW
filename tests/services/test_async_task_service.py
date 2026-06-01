"""
AsyncTaskService 单元测试
=========================

验证异步任务提交、状态查询、取消等职责已完全从 GenerationService 中剥离。

测试策略：
  1. mock Celery 任务对象，避免真实 broker 依赖。
  2. 使用内存数据库验证 GenerationJob 持久化行为。
  3. 验证 DTO 边界（输入 Dict -> DTO -> Service）。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from services.async_task_service import (
    AsyncBatchSubmitDto,
    AsyncTaskError,
    AsyncTaskService,
    AsyncTaskSubmitDto,
    TaskStatusDto,
)
from services.base.permission_manager import PermissionDenied
from vcw_copywriter.db.models import GenerationJob
from vcw_copywriter.db.session import get_session


@pytest.fixture(autouse=True)
def ensure_db(app):
    """确保内存数据库表已创建（复用 session 级 app fixture）。"""
    pass


@pytest.fixture
def svc():
    """无权限管理器的 AsyncTaskService 实例。"""
    return AsyncTaskService(permission_manager=None)


@pytest.fixture
def svc_with_pm():
    """带权限管理器的 AsyncTaskService 实例。"""
    pm = MagicMock()
    return AsyncTaskService(permission_manager=pm), pm


class TestSubmitAsyncGenerate:
    """单任务提交测试。"""

    def test_submit_success(self, svc, monkeypatch):
        """正常提交后返回 task_id 并在 DB 中创建记录。"""

        class MockAsyncResult:
            id = "mock-task-abc123"

        def mock_delay(*args, **kwargs):
            return MockAsyncResult()

        monkeypatch.setattr(
            "vcw_celery_tasks.tasks.generate_copy_task.delay",
            mock_delay,
        )

        dto = AsyncTaskSubmitDto(req_data={"topic": "测试主题", "audience": "港宝家长"})
        task_id = svc.submit_async_generate(dto)

        assert task_id == "mock-task-abc123"

        # 验证 DB 记录
        session = get_session()
        try:
            job = (
                session.query(GenerationJob)
                .filter(GenerationJob.celery_task_id == task_id)
                .first()
            )
            assert job is not None
            assert job.job_type == "generate"
            assert job.status == "pending"
        finally:
            session.close()

    def test_submit_requires_topic(self, svc):
        """缺少主题抛出 AsyncTaskError。"""
        dto = AsyncTaskSubmitDto(req_data={"topic": "", "audience": "港宝家长"})
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.submit_async_generate(dto)
        assert exc_info.value.code == "MISSING_TOPIC"

    def test_submit_permission_denied(self, svc_with_pm, monkeypatch):
        """权限不足时抛出 AsyncTaskError。"""
        svc, pm = svc_with_pm
        pm.check.side_effect = PermissionDenied("无权限", code="FORBIDDEN")

        dto = AsyncTaskSubmitDto(req_data={"topic": "测试主题"})
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.submit_async_generate(dto)
        assert exc_info.value.code == "FORBIDDEN"


class TestGetAsyncStatus:
    """单任务状态查询测试。"""

    def test_get_status_success(self, svc, monkeypatch):
        """查询已存在的任务返回 TaskStatusDto。"""

        class MockAsyncResult:
            state = "SUCCESS"
            result = {"content": "mocked"}
            date_done = datetime(2024, 1, 1, 12, 0, 0)

        monkeypatch.setattr(
            "celery.result.AsyncResult",
            lambda task_id, app: MockAsyncResult(),
        )

        # 预创建 DB 记录
        session = get_session()
        try:
            job = GenerationJob(
                id="job-001",
                job_type="generate",
                status="pending",
                celery_task_id="task-001",
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        status = svc.get_async_status("task-001")
        assert isinstance(status, TaskStatusDto)
        assert status.id == "task-001"
        assert status.status == "completed"
        assert status.progress == 100
        assert status.completed_at == "2024-01-01 12:00:00"

    def test_get_status_not_found(self, svc):
        """查询不存在的任务抛出 AsyncTaskError。"""
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.get_async_status("nonexistent-id")
        assert exc_info.value.code == "TASK_NOT_FOUND"

    def test_get_status_running(self, svc, monkeypatch):
        """任务运行中状态映射正确。"""

        class MockAsyncResult:
            state = "STARTED"
            result = None
            date_done = None

        monkeypatch.setattr(
            "celery.result.AsyncResult",
            lambda task_id, app: MockAsyncResult(),
        )

        session = get_session()
        try:
            job = GenerationJob(
                id="job-002",
                job_type="generate",
                status="pending",
                celery_task_id="task-002",
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        status = svc.get_async_status("task-002")
        assert status.status == "running"
        assert status.progress == 10


class TestCancelAsyncTask:
    """单任务取消测试。"""

    def test_cancel_success(self, svc, monkeypatch):
        """取消任务返回 True 并调用 revoke。"""
        revoke_called = []

        class MockControl:
            def revoke(self, task_id, terminate=False):
                revoke_called.append(task_id)

        class MockApp:
            control = MockControl()

        monkeypatch.setattr(
            "celery_app.app",
            MockApp(),
        )

        ok = svc.cancel_async_task("task-003")
        assert ok is True
        assert revoke_called == ["task-003"]


class TestSubmitAsyncBatch:
    """批量任务提交测试。"""

    def test_submit_success(self, svc, monkeypatch):
        """正常提交后返回 batch_id 并在 DB 中创建父批次记录。"""

        class MockAsyncResult:
            id = "mock-batch-xyz789"

        def mock_delay(*args, **kwargs):
            return MockAsyncResult()

        monkeypatch.setattr(
            "vcw_celery_tasks.tasks.generate_batch_task.delay",
            mock_delay,
        )

        dto = AsyncBatchSubmitDto(
            req_data={"topic": "测试主题", "audience": "港宝家长"},
            angles=["焦虑型", "数据型"],
        )
        batch_id = svc.submit_async_batch(dto)

        assert batch_id

        session = get_session()
        try:
            parent = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == batch_id)
                .first()
            )
            assert parent is not None
            assert parent.job_type == "batch"
            assert parent.status == "pending"
            result = parent.result or {}
            assert result.get("total") == 2
        finally:
            session.close()

    def test_submit_requires_topic(self, svc):
        """缺少主题抛出 AsyncTaskError。"""
        dto = AsyncBatchSubmitDto(
            req_data={"topic": ""},
            angles=["焦虑型"],
        )
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.submit_async_batch(dto)
        assert exc_info.value.code == "MISSING_TOPIC"

    def test_submit_requires_angles(self, svc):
        """缺少角度抛出 AsyncTaskError。"""
        dto = AsyncBatchSubmitDto(
            req_data={"topic": "测试主题"},
            angles=[],
        )
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.submit_async_batch(dto)
        assert exc_info.value.code == "MISSING_ANGLES"


class TestGetAsyncBatchStatus:
    """批量任务状态查询测试。"""

    def test_get_status_success(self, svc):
        """查询已存在的批次返回聚合状态。"""
        batch_id = "batch-001"

        session = get_session()
        try:
            parent = GenerationJob(
                id=batch_id,
                job_type="batch",
                status="running",
                result={"total": 2, "completed": 0, "failed": 0, "cancelled": 0},
                created_at=datetime.utcnow(),
            )
            session.add(parent)

            child1 = GenerationJob(
                id="child-001",
                job_type="generate",
                status="completed",
                parent_batch_id=batch_id,
                result={"angle": "焦虑型"},
                created_at=datetime.utcnow(),
            )
            child2 = GenerationJob(
                id="child-002",
                job_type="generate",
                status="failed",
                parent_batch_id=batch_id,
                result={"angle": "数据型"},
                error="模拟错误",
                created_at=datetime.utcnow(),
            )
            session.add(child1)
            session.add(child2)
            session.commit()
        finally:
            session.close()

        status = svc.get_async_batch_status(batch_id)
        assert status["batch_id"] == batch_id
        assert status["status"] == "partial"
        assert status["total"] == 2
        assert status["completed"] == 1
        assert status["failed"] == 1
        assert len(status["items"]) == 2

    def test_get_status_not_found(self, svc):
        """查询不存在的批次抛出 AsyncTaskError。"""
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.get_async_batch_status("nonexistent-batch")
        assert exc_info.value.code == "BATCH_NOT_FOUND"


class TestCancelAsyncBatch:
    """批量任务取消测试。"""

    def test_cancel_success(self, svc, monkeypatch):
        """取消批次及其子任务，返回 True。"""
        batch_id = "batch-002"
        revoked = []

        class MockControl:
            def revoke(self, task_id, terminate=False):
                revoked.append(task_id)

        class MockApp:
            control = MockControl()

        monkeypatch.setattr(
            "celery_app.app",
            MockApp(),
        )

        session = get_session()
        try:
            parent = GenerationJob(
                id=batch_id,
                job_type="batch",
                status="running",
                created_at=datetime.utcnow(),
            )
            session.add(parent)

            child = GenerationJob(
                id="child-003",
                job_type="generate",
                status="pending",
                parent_batch_id=batch_id,
                celery_task_id="celery-child-003",
                created_at=datetime.utcnow(),
            )
            session.add(child)
            session.commit()
        finally:
            session.close()

        ok = svc.cancel_async_batch(batch_id)
        assert ok is True
        assert revoked == ["celery-child-003"]

        # 验证 DB 状态更新
        session = get_session()
        try:
            parent = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == batch_id)
                .first()
            )
            assert parent.status == "cancelled"

            child = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == "child-003")
                .first()
            )
            assert child.status == "cancelled"
        finally:
            session.close()

    def test_cancel_not_found(self, svc):
        """取消不存在的批次抛出 AsyncTaskError。"""
        with pytest.raises(AsyncTaskError) as exc_info:
            svc.cancel_async_batch("nonexistent-batch")
        assert exc_info.value.code == "BATCH_NOT_FOUND"

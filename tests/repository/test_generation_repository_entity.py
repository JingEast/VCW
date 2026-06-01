"""
GenerationJob Repository → Entity 隔离测试
==========================================

验证从数据库查询到最终返回给 service 的全链路中，
ORM 对象不会泄漏到业务逻辑层。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from domains.generation.domain.entities import GenerationJobEntity
from domains.generation.infrastructure.generation_mapper import GenerationJobMapper
from vcw_copywriter.db.models import GenerationJob
from vcw_copywriter.db.session import get_session


@pytest.fixture(autouse=True)
def ensure_db(app):
    """确保内存数据库表已创建。"""
    pass


class TestRepositoryReturnsEntity:
    """Repository 边界返回纯领域实体验证。"""

    def test_query_then_map_returns_entity(self):
        """先写入 ORM，再查询并映射，得到的是纯实体。"""
        session = get_session()
        try:
            orm = GenerationJob(
                id="repo-001",
                job_type="generate",
                status="running",
                progress=42,
                message="测试中",
                result={"key": "value"},
                error="",
                created_at=datetime.utcnow(),
                celery_task_id="task-repo-001",
            )
            session.add(orm)
            session.commit()
        finally:
            session.close()

        # 模拟 Repository 的查询 + 映射边界
        session = get_session()
        try:
            orm = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == "repo-001")
                .first()
            )
            entity = GenerationJobMapper.to_entity(orm)
        finally:
            session.close()

        assert isinstance(entity, GenerationJobEntity)
        assert entity.id == "repo-001"
        assert entity.status == "running"
        assert entity.progress == 42
        # 关键：entity 不应携带任何 ORM 状态
        assert not hasattr(entity, "_sa_instance_state")

    def test_entity_has_no_lazy_loading(self):
        """实体在 session 关闭后仍可安全访问所有字段。"""
        session = get_session()
        try:
            orm = GenerationJob(
                id="repo-002",
                job_type="batch",
                status="pending",
                result={"total": 10},
                created_at=datetime.utcnow(),
            )
            session.add(orm)
            session.commit()
        finally:
            session.close()

        # session 已关闭，模拟 Service 拿到 entity 后的场景
        session = get_session()
        try:
            orm = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == "repo-002")
                .first()
            )
            entity = GenerationJobMapper.to_entity(orm)
        finally:
            session.close()

        # session 关闭后访问 entity 字段不应触发 lazy loading
        assert entity.id == "repo-002"
        assert entity.job_type == "batch"
        assert entity.result == {"total": 10}
        assert entity.created_at is not None

    def test_entity_can_be_created_without_db(self):
        """领域实体可完全脱离数据库独立构造。"""
        entity = GenerationJobEntity(
            id="repo-003",
            job_type="generate",
            status="completed",
            progress=100,
            message="完成",
            result={"content": "文案内容"},
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )

        assert entity.id == "repo-003"
        assert entity.progress == 100
        assert entity.result["content"] == "文案内容"
        # 不依赖任何 session、engine 或 ORM 基础设施

    def test_round_trip_persists_correctly(self):
        """Entity → ORM → DB → ORM → Entity 往返无损。"""
        original = GenerationJobEntity(
            id="repo-004",
            job_type="generate",
            status="failed",
            progress=80,
            message="部分完成",
            result={"partial": True},
            error="网络超时",
            created_at=datetime(2024, 3, 15, 10, 30, 0),
            started_at=datetime(2024, 3, 15, 10, 31, 0),
            completed_at=datetime(2024, 3, 15, 10, 35, 0),
            retry_count=2,
            max_retries=3,
            dead_letter=True,
            celery_task_id="ct-004",
            parent_batch_id="batch-004",
        )

        # 写入
        session = get_session()
        try:
            orm = GenerationJobMapper.to_orm(original)
            session.add(orm)
            session.commit()
        finally:
            session.close()

        # 读取
        session = get_session()
        try:
            orm = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == "repo-004")
                .first()
            )
            restored = GenerationJobMapper.to_entity(orm)
        finally:
            session.close()

        assert restored.id == original.id
        assert restored.job_type == original.job_type
        assert restored.status == original.status
        assert restored.progress == original.progress
        assert restored.message == original.message
        assert restored.result == original.result
        assert restored.error == original.error
        assert restored.created_at == original.created_at
        assert restored.started_at == original.started_at
        assert restored.completed_at == original.completed_at
        assert restored.retry_count == original.retry_count
        assert restored.max_retries == original.max_retries
        assert restored.dead_letter == original.dead_letter
        assert restored.celery_task_id == original.celery_task_id
        assert restored.parent_batch_id == original.parent_batch_id

    def test_batch_status_aggregation_with_entities(self):
        """使用纯实体进行批量状态聚合，无需 ORM。"""
        session = get_session()
        try:
            parent_orm = GenerationJob(
                id="batch-repo-005",
                job_type="batch",
                status="running",
                created_at=datetime.utcnow(),
            )
            session.add(parent_orm)

            for i, st in enumerate(["completed", "failed", "pending"]):
                child_orm = GenerationJob(
                    id=f"child-repo-005-{i}",
                    job_type="generate",
                    status=st,
                    parent_batch_id="batch-repo-005",
                    result={"angle": f"角度{i}"},
                    created_at=datetime.utcnow(),
                )
                session.add(child_orm)

            session.commit()
        finally:
            session.close()

        # 模拟 Repository 查询并映射为实体
        session = get_session()
        try:
            parent_orm = (
                session.query(GenerationJob)
                .filter(GenerationJob.id == "batch-repo-005")
                .first()
            )
            children_orm = (
                session.query(GenerationJob)
                .filter(GenerationJob.parent_batch_id == "batch-repo-005")
                .all()
            )
            parent = GenerationJobMapper.to_entity(parent_orm)
            children = [GenerationJobMapper.to_entity(c) for c in children_orm]
        finally:
            session.close()

        # 纯实体聚合逻辑（与 AsyncTaskService 中一致）
        total = len(children)
        completed = sum(1 for c in children if c.status == "completed")
        failed = sum(1 for c in children if c.status == "failed")
        pending = sum(1 for c in children if c.status == "pending")

        assert total == 3
        assert completed == 1
        assert failed == 1
        assert pending == 1
        assert parent.id == "batch-repo-005"
        assert parent.job_type == "batch"
        # 关键：聚合过程完全不依赖 ORM
        for child in children:
            assert not hasattr(child, "_sa_instance_state")

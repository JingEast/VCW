"""
GenerationJob Mapper 单元测试
==============================

验证 Mapper 在 ORM 与纯领域实体之间的双向转换无信息丢失，
且不引入任何 session 或 lazy-loading 依赖。
"""

from __future__ import annotations

from datetime import datetime

from domains.generation.domain.entities import GenerationJobEntity
from domains.generation.infrastructure.generation_mapper import GenerationJobMapper
from vcw_copywriter.db.models import GenerationJob


class TestToEntity:
    """ORM → Entity 转换测试。"""

    def test_full_mapping(self):
        """所有字段完整映射，无丢失。"""
        orm = GenerationJob(
            id="job-001",
            job_type="generate",
            status="running",
            progress=50,
            message="测试中...",
            result={"angle": "焦虑型"},
            error="",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            started_at=datetime(2024, 1, 1, 10, 1, 0),
            completed_at=datetime(2024, 1, 1, 10, 5, 0),
            retry_count=1,
            max_retries=5,
            dead_letter=True,
            celery_task_id="celery-abc",
            parent_batch_id="batch-001",
        )

        entity = GenerationJobMapper.to_entity(orm)

        assert isinstance(entity, GenerationJobEntity)
        assert entity.id == "job-001"
        assert entity.job_type == "generate"
        assert entity.status == "running"
        assert entity.progress == 50
        assert entity.message == "测试中..."
        assert entity.result == {"angle": "焦虑型"}
        assert entity.error == ""
        assert entity.created_at == datetime(2024, 1, 1, 10, 0, 0)
        assert entity.started_at == datetime(2024, 1, 1, 10, 1, 0)
        assert entity.completed_at == datetime(2024, 1, 1, 10, 5, 0)
        assert entity.retry_count == 1
        assert entity.max_retries == 5
        assert entity.dead_letter is True
        assert entity.celery_task_id == "celery-abc"
        assert entity.parent_batch_id == "batch-001"

    def test_none_defaults(self):
        """ORM 字段为 None 时，映射后使用合理默认值。"""
        orm = GenerationJob(
            id="job-002",
            job_type="batch",
            status=None,
            progress=None,
            message=None,
            result=None,
            error=None,
            created_at=None,
            started_at=None,
            completed_at=None,
            retry_count=None,
            max_retries=None,
            dead_letter=None,
            celery_task_id=None,
            parent_batch_id=None,
        )

        entity = GenerationJobMapper.to_entity(orm)

        assert entity.status == "pending"
        assert entity.progress == 0
        assert entity.message == ""
        assert entity.result == {}
        assert entity.error == ""
        assert entity.created_at is None
        assert entity.started_at is None
        assert entity.completed_at is None
        assert entity.retry_count == 0
        assert entity.max_retries == 3
        assert entity.dead_letter is False
        assert entity.celery_task_id is None
        assert entity.parent_batch_id is None

    def test_entity_is_pure(self):
        """转换后的实体不应携带任何 ORM 状态。"""
        orm = GenerationJob(id="job-003", job_type="generate")
        entity = GenerationJobMapper.to_entity(orm)

        # 纯 dataclass 不应有 SQLAlchemy 的 _sa_instance_state
        assert not hasattr(entity, "_sa_instance_state")
        assert not hasattr(entity, "__mapper__")
        assert type(entity).__name__ == "GenerationJobEntity"


class TestToOrm:
    """Entity → ORM 转换测试。"""

    def test_full_mapping(self):
        """所有字段完整映射到 ORM，无丢失。"""
        entity = GenerationJobEntity(
            id="job-004",
            job_type="batch",
            status="completed",
            progress=100,
            message="完成",
            result={"total": 5},
            error="",
            created_at=datetime(2024, 6, 1, 12, 0, 0),
            started_at=datetime(2024, 6, 1, 12, 1, 0),
            completed_at=datetime(2024, 6, 1, 12, 5, 0),
            retry_count=0,
            max_retries=3,
            dead_letter=False,
            celery_task_id="celery-xyz",
            parent_batch_id="batch-002",
        )

        orm = GenerationJobMapper.to_orm(entity)

        assert isinstance(orm, GenerationJob)
        assert orm.id == "job-004"
        assert orm.job_type == "batch"
        assert orm.status == "completed"
        assert orm.progress == 100
        assert orm.message == "完成"
        assert orm.result == {"total": 5}
        assert orm.error == ""
        assert orm.created_at == datetime(2024, 6, 1, 12, 0, 0)
        assert orm.started_at == datetime(2024, 6, 1, 12, 1, 0)
        assert orm.completed_at == datetime(2024, 6, 1, 12, 5, 0)
        assert orm.retry_count == 0
        assert orm.max_retries == 3
        assert orm.dead_letter is False
        assert orm.celery_task_id == "celery-xyz"
        assert orm.parent_batch_id == "batch-002"

    def test_orm_is_detached(self):
        """新转换的 ORM 实例未附加到任何 session。"""
        entity = GenerationJobEntity(
            id="job-005",
            job_type="generate",
        )
        orm = GenerationJobMapper.to_orm(entity)

        from sqlalchemy import inspect as sa_inspect
        assert sa_inspect(orm).detached is False  # 新实例未附加到 session
        assert sa_inspect(orm).persistent is False
        assert sa_inspect(orm).transient is True


class TestUpdateOrm:
    """Entity → 已有 ORM 同步测试。"""

    def test_update_fields(self):
        """update_orm 将实体状态正确同步到已有 ORM 实例。"""
        orm = GenerationJob(
            id="job-006",
            job_type="generate",
            status="pending",
            progress=0,
            message="等待中",
            result={},
            error="",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            started_at=None,
            completed_at=None,
            retry_count=0,
            max_retries=3,
            dead_letter=False,
            celery_task_id=None,
            parent_batch_id=None,
        )

        entity = GenerationJobEntity(
            id="job-006",
            job_type="generate",
            status="failed",
            progress=100,
            message="失败",
            result={"error": "oom"},
            error="Out of memory",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            started_at=datetime(2024, 1, 1, 0, 1, 0),
            completed_at=datetime(2024, 1, 1, 0, 2, 0),
            retry_count=3,
            max_retries=5,
            dead_letter=True,
            celery_task_id="celery-123",
            parent_batch_id="batch-003",
        )

        GenerationJobMapper.update_orm(entity, orm)

        assert orm.status == "failed"
        assert orm.progress == 100
        assert orm.message == "失败"
        assert orm.result == {"error": "oom"}
        assert orm.error == "Out of memory"
        assert orm.started_at == datetime(2024, 1, 1, 0, 1, 0)
        assert orm.completed_at == datetime(2024, 1, 1, 0, 2, 0)
        assert orm.retry_count == 3
        assert orm.dead_letter is True
        assert orm.celery_task_id == "celery-123"
        assert orm.parent_batch_id == "batch-003"

        # 不可变字段不应被覆盖
        assert orm.id == "job-006"
        assert orm.job_type == "generate"
        assert orm.created_at == datetime(2024, 1, 1, 0, 0, 0)
        assert orm.max_retries == 3

    def test_update_does_not_create_new_instance(self):
        """update_orm 修改传入的 ORM 实例，不返回新对象。"""
        orm = GenerationJob(id="job-007", job_type="generate", status="pending")
        orm_id = id(orm)

        entity = GenerationJobEntity(
            id="job-007",
            job_type="generate",
            status="completed",
        )

        GenerationJobMapper.update_orm(entity, orm)

        assert id(orm) == orm_id
        assert orm.status == "completed"

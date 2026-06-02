"""
SQLAlchemy ORM 模型
定义 4 个核心实体：Trend / MemoryEntry / GenerationJob / GenerationResult
"""

from app.core.datetime_utils import utc_now
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, JSON, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, mapped_column

Base = declarative_base()


class Trend(Base):  # type: ignore[valid-type, misc]
    """热点话题实体（原 trend_db.json 中的 trends 数组）"""
    __tablename__ = "trends"

    id = Column(String(16), primary_key=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, default="")
    source = Column(String(100), default="")
    url = Column(Text, default="")
    category = Column(String(50), default="未分类")
    tags = Column(JSON, default=list)
    relevance_score = Column(Integer, default=50)
    click_count = Column(Integer, default=0)
    is_selected = Column(Boolean, default=False)
    is_manual = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    time_source = Column(String(50), default="")          # 原 _time_source
    keyword = Column(String(200), default="")
    composite_score = Column(Integer, nullable=True)       # 运行时计算，可缓存
    timeliness_score = Column(Integer, nullable=True)      # 运行时计算，可缓存
    is_stale = Column(Boolean, nullable=True)              # 运行时计算，可缓存
    embedding = mapped_column(Vector(1536), nullable=True)  # pgvector 语义向量

    def to_dict(self) -> dict:
        """转换为与原 JSON 结构兼容的字典"""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "url": self.url,
            "category": self.category,
            "tags": self.tags or [],
            "relevance_score": self.relevance_score or 0,
            "click_count": self.click_count or 0,
            "is_selected": bool(self.is_selected),
            "is_manual": bool(self.is_manual),
            "published_at": self.published_at.strftime("%Y-%m-%d %H:%M") if self.published_at else "",
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
            "_time_source": self.time_source or "",
            "keyword": self.keyword or "",
            "composite_score": self.composite_score,
            "timeliness_score": self.timeliness_score,
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Trend":
        """从原 JSON 字典创建 ORM 实例"""
        from ..scraper.utils import TimeParser

        def _dt(val):
            if not val:
                return None
            dt = TimeParser.parse_datetime(val)
            return dt if dt else None

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            source=data.get("source", ""),
            url=data.get("url", ""),
            category=data.get("category", "未分类"),
            tags=data.get("tags") or [],
            relevance_score=data.get("relevance_score", 50),
            click_count=data.get("click_count", 0),
            is_selected=bool(data.get("is_selected")),
            is_manual=bool(data.get("is_manual")),
            is_archived=bool(data.get("is_archived")),
            published_at=_dt(data.get("published_at")),
            fetched_at=_dt(data.get("fetched_at")),
            created_at=_dt(data.get("created_at")) or utc_now(),
            updated_at=_dt(data.get("updated_at")) or utc_now(),
            time_source=data.get("_time_source", ""),
            keyword=data.get("keyword", ""),
        )


class MemoryEntry(Base):  # type: ignore[valid-type, misc]
    """记忆库条目实体（原 memory_db.json 中的 entries 数组）"""
    __tablename__ = "memory_entries"

    id = Column(String(16), primary_key=True)
    topic = Column(String(200), nullable=False, index=True)
    issue_description = Column(Text, nullable=False)
    issue_tags = Column(JSON, default=list)
    correction_plan = Column(Text, default="")
    original_text = Column(Text, default="")
    created_at = Column(DateTime, default=utc_now)
    is_avoided = Column(Boolean, default=False)
    embedding = mapped_column(Vector(1536), nullable=True)  # pgvector 语义向量

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "issue_description": self.issue_description,
            "issue_tags": self.issue_tags or [],
            "correction_plan": self.correction_plan,
            "original_text": self.original_text,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "is_avoided": bool(self.is_avoided),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        from ..scraper.utils import TimeParser

        def _dt(val):
            if not val:
                return None
            dt = TimeParser.parse_datetime(val)
            return dt if dt else None

        return cls(
            id=data.get("id", ""),
            topic=data.get("topic", ""),
            issue_description=data.get("issue_description", ""),
            issue_tags=data.get("issue_tags") or [],
            correction_plan=data.get("correction_plan", ""),
            original_text=data.get("original_text", ""),
            created_at=_dt(data.get("created_at")) or utc_now(),
            is_avoided=bool(data.get("is_avoided")),
        )


class GenerationJob(Base):  # type: ignore[valid-type, misc]
    """生成任务实体（原 task_queue.db 中的 tasks 表）"""
    __tablename__ = "generation_jobs"

    id = Column(String(16), primary_key=True)
    job_type = Column(String(50), nullable=False)      # 原 type
    status = Column(String(20), default="pending")     # pending/running/completed/failed/cancelled
    progress = Column(Integer, default=0)
    message = Column(Text, default="")
    result = Column(JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=utc_now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    dead_letter = Column(Boolean, default=False)
    celery_task_id = Column(String(50), nullable=True)
    parent_batch_id = Column(String(50), nullable=True, index=True)

    def to_dict(self) -> dict:
        def _fmt(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None
        return {
            "id": self.id,
            "type": self.job_type,
            "status": self.status,
            "progress": self.progress or 0,
            "message": self.message or "",
            "result": self.result or {},
            "error": self.error or "",
            "created_at": _fmt(self.created_at),
            "started_at": _fmt(self.started_at),
            "completed_at": _fmt(self.completed_at),
        }

    @classmethod
    def from_legacy_sqlite_row(cls, row: tuple) -> "GenerationJob":
        """从原 SQLite row tuple 创建 ORM 实例
        row 格式: (id, type, status, progress, message, result, error, created_at, started_at, completed_at)
        """
        def _dt(ts):
            from datetime import datetime as _dt_cls
            return _dt_cls.fromtimestamp(ts) if ts else None

        return cls(
            id=row[0],
            job_type=row[1],
            status=row[2],
            progress=row[3] or 0,
            message=row[4] or "",
            result=__import__("json").loads(row[5]) if row[5] else {},
            error=row[6] or "",
            created_at=_dt(row[7]),
            started_at=_dt(row[8]),
            completed_at=_dt(row[9]),
        )


class PromptVersion(Base):  # type: ignore[valid-type, misc]
    """Prompt 版本控制实体（用于追踪每次 Prompt 变更历史）"""
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_name = Column(String(200), nullable=False, index=True)   # 如 "system_prompt", "viral_rewrite"
    version = Column(String(50), nullable=False)                     # 语义版本号，如 "v1.2.0"
    content = Column(Text, nullable=False)                           # Prompt 完整文本
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("prompt_name", "version", name="uq_prompt_version"),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt_name": self.prompt_name,
            "version": self.version,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class GenerationResult(Base):  # type: ignore[valid-type, misc]
    """生成结果实体（原 data/generated/*.md 文件）"""
    __tablename__ = "generation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(Text, default="")
    filepath = Column(Text, default="")
    draft_id = Column(String(16), default="")
    passed = Column(Boolean, nullable=True)
    report = Column(Text, default="")
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "content": self.content,
            "meta": self.meta,
            "filepath": self.filepath,
            "draft_id": self.draft_id,
            "passed": self.passed,
            "report": self.report,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }

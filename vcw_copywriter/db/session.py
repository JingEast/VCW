"""
SQLAlchemy Session 管理
支持 PostgreSQL（生产）和 SQLite（开发/测试）自动切换。
通过环境变量 DATABASE_URL 配置连接字符串。
"""
import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

# 优先使用环境变量 DATABASE_URL，否则回退到本地 SQLite
DEFAULT_DATABASE_URL = "sqlite:///data/vcw.db"


def _get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


# 向后兼容：允许旧代码直接 import DATABASE_URL
# 注意：模块导入后该值不会再随环境变量变化；需要动态读取请使用 _get_database_url()
DATABASE_URL = _get_database_url()


def _make_engine_kwargs(database_url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    if database_url.startswith("sqlite:///:memory:"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    elif database_url.startswith("postgresql"):
        kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
        kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
    return kwargs


# Lazy engine：在首次使用时创建，避免 pytest-cov 预先导入时捕获错误的环境变量
_engine = None


def get_engine():
    """获取或创建 SQLAlchemy engine（支持运行时 DATABASE_URL 变化）。"""
    global _engine
    if _engine is None:
        database_url = _get_database_url()
        _engine = create_engine(
            database_url,
            **_make_engine_kwargs(database_url),
        )
    return _engine


def reset_engine():
    """重置 engine（用于测试环境切换数据库）。"""
    global _engine
    _engine = None


# 兼容旧代码直接引用 engine（首次访问时惰性初始化）
class _EngineProxy:
    """代理对象，允许旧代码通过 module.engine 访问当前 engine。"""
    def __getattr__(self, name):
        return getattr(get_engine(), name)

    def __setattr__(self, name, value):
        setattr(get_engine(), name, value)

    def __call__(self, *args, **kwargs):
        return get_engine()(*args, **kwargs)


engine = _EngineProxy()  # type: ignore[assignment]


# 延迟绑定的 sessionmaker（每次调用时引用当前 engine）
def _sessionmaker():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


SessionLocal = _sessionmaker()
ScopedSession = scoped_session(SessionLocal)


def get_session():
    """获取一个新的数据库 Session（调用方负责关闭）"""
    return SessionLocal()


def init_db():
    """创建所有表（如果不存在）。PostgreSQL 下自动启用 pgvector 扩展。"""
    from .models import Base
    _engine = get_engine()
    database_url = _get_database_url()
    if database_url.startswith("postgresql"):
        with _engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=_engine)
    print(f"[DB] 数据库初始化完成: {database_url}")

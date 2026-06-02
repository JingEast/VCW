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
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

# SQLite :memory: 需要 StaticPool，否则每次新连接都是空数据库
_is_memory_sqlite = DATABASE_URL.startswith("sqlite:///:memory:")
_is_postgresql = DATABASE_URL.startswith("postgresql")

_engine_kwargs: dict[str, Any] = {
    "echo": False,
    "pool_pre_ping": True,          # 自动检测断连
    "pool_recycle": 3600,           # 1 小时回收连接
}
if _is_memory_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
elif _is_postgresql:
    # 生产环境连接池：基础 10 个连接，峰值 30 个
    _engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
    _engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))

engine = create_engine(
    DATABASE_URL,
    **_engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(SessionLocal)


def get_session():
    """获取一个新的数据库 Session（调用方负责关闭）"""
    return SessionLocal()


def init_db():
    """创建所有表（如果不存在）。PostgreSQL 下自动启用 pgvector 扩展。"""
    from .models import Base
    if DATABASE_URL.startswith("postgresql"):
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    print(f"[DB] 数据库初始化完成: {DATABASE_URL}")

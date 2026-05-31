"""
SQLAlchemy Session 管理
支持 PostgreSQL（生产）和 SQLite（开发/测试）自动切换。
通过环境变量 DATABASE_URL 配置连接字符串。
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

# 优先使用环境变量 DATABASE_URL，否则回退到本地 SQLite
DEFAULT_DATABASE_URL = "sqlite:///data/vcw.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,          # 自动检测断连
    pool_recycle=3600,           # 1 小时回收连接
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

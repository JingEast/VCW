"""
Alembic 环境配置

支持 PostgreSQL（通过 DATABASE_URL 环境变量）和 SQLite（回退）。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 将项目根目录加入 sys.path，确保模型可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 导入 SQLAlchemy Base 与数据库 URL
from vcw_copywriter.db.models import Base
from vcw_copywriter.db.session import _get_database_url

# this is the Alembic Config object
config = context.config

# 动态注入数据库连接字符串（优先环境变量，其次 session 模块中的默认值）
DATABASE_URL = _get_database_url()
config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", DATABASE_URL))

# Interpret the Python file for logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata 用于 autogenerate 支持
target_metadata = Base.metadata


def _compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """自定义类型比较，处理 pgvector VECTOR 未实现 __eq__ 的问题。"""
    # pgvector.sqlalchemy.Vector 返回的 VECTOR 实例使用默认 object.__eq__，
    # 导致两个 dim 相同的实例永远不相等，alembic check 会误判为 schema drift。
    meta_cls = metadata_type.__class__.__name__
    insp_cls = inspected_type.__class__.__name__
    if meta_cls == "VECTOR" and insp_cls == "VECTOR":
        return getattr(metadata_type, "dim", None) != getattr(inspected_type, "dim", None)
    # 其他类型使用 Alembic 默认比较逻辑
    return None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url") or ""
    is_sqlite = url.startswith("sqlite://")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=False if is_sqlite else _compare_type,
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False if is_sqlite else _compare_type,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
Alembic 环境配置

支持 PostgreSQL（通过 DATABASE_URL 环境变量）和 SQLite（回退）。
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 将项目根目录加入 sys.path，确保模型可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 导入 SQLAlchemy Base 与数据库 URL
from vcw_copywriter.db.models import Base
from vcw_copywriter.db.session import DATABASE_URL

# this is the Alembic Config object
config = context.config

# 动态注入数据库连接字符串（优先环境变量，其次 session 模块中的默认值）
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata 用于 autogenerate 支持
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

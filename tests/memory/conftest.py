"""
Memory tests 局部 fixtures
确保每个 pytest-xdist worker 在运行 memory 测试前初始化数据库表。
"""

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_memory_db_tables():
    from vcw_copywriter.db.session import init_db
    init_db()

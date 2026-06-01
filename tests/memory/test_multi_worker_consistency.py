"""
多 Worker 一致性测试
验证 MemoryBank 不再持有进程内 self.data，
多个独立实例（模拟多个 worker 进程）共享同一 PostgreSQL 真相源。
"""
import pytest
from vcw_copywriter.memory import MemoryBank
from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.repositories.memory_repository import MemoryRepository


def _clear_all_entries():
    session = get_session()
    repo = MemoryRepository(session)
    for e in session.query(repo.model).all():
        session.delete(e)
    session.commit()
    session.close()


@pytest.fixture(autouse=True)
def clean_db():
    _clear_all_entries()
    yield
    _clear_all_entries()


def test_worker_a_adds_worker_b_sees():
    """Worker A 添加条目后，Worker B 应立即可见。"""
    worker_a = MemoryBank(db_path="data/memory_db.json")
    eid = worker_a.add_entry(
        topic="共享主题",
        issue_description="问题描述",
        issue_tags=["一致性"],
        correction_plan="修正",
    )

    worker_b = MemoryBank(db_path="data/memory_db.json")
    entries = worker_b.get_entries_by_topic("共享主题", limit=10)
    assert len(entries) == 1
    assert entries[0]["id"] == eid


def test_worker_b_deletes_worker_a_reads_empty():
    """Worker B 删除条目后，Worker A 再次查询应返回空。"""
    worker_a = MemoryBank(db_path="data/memory_db.json")
    eid = worker_a.add_entry(
        topic="临时主题",
        issue_description="d",
        issue_tags=[],
        correction_plan="c",
    )

    worker_b = MemoryBank(db_path="data/memory_db.json")
    assert worker_b.delete_entry(eid) is True

    # Worker A 重新查询数据库（不依赖本地缓存）
    # 注意：get_entries_by_topic 包含向量检索 fallback，可能命中旧索引；
    # 因此使用 get_recent_entries / get_entry_count 验证 DB 一致性。
    assert worker_a.get_entry_count() == 0
    assert len(worker_a.get_recent_entries(limit=10)) == 0


def test_worker_b_avoids_worker_a_sees():
    """Worker B 标记规避后，Worker A 的 pending count 应下降。"""
    worker_a = MemoryBank(db_path="data/memory_db.json")
    eid = worker_a.add_entry(
        topic="T", issue_description="d", issue_tags=[], correction_plan="c"
    )
    assert worker_a.get_pending_count() == 1

    worker_b = MemoryBank(db_path="data/memory_db.json")
    worker_b.mark_avoided(eid)

    assert worker_a.get_pending_count() == 0

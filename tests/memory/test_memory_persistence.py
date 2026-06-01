"""
MemoryBank 持久化测试
验证 MemoryBank 适配器所有公共方法均通过 PostgreSQL 读写，
不再依赖进程内 self.data 缓存。
"""
import pytest
from vcw_copywriter.memory import MemoryBank
from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.repositories.memory_repository import MemoryRepository


@pytest.fixture
def fresh_memory_bank():
    """每次返回全新 MemoryBank 实例，确保从数据库重新加载。"""
    bank = MemoryBank(db_path="data/memory_db.json")
    # 清理数据库，保证隔离
    session = get_session()
    repo = MemoryRepository(session)
    for e in session.query(repo.model).all():
        session.delete(e)
    session.commit()
    session.close()
    yield bank


def test_add_and_get_recent(fresh_memory_bank):
    bank = fresh_memory_bank
    eid = bank.add_entry(
        topic="升学文案",
        issue_description="描述过长",
        issue_tags=["风格"],
        correction_plan="精简",
        original_text="原始文本",
    )
    assert eid

    entries = bank.get_recent_entries(limit=10)
    assert len(entries) == 1
    assert entries[0]["topic"] == "升学文案"
    assert entries[0]["issue_tags"] == ["风格"]


def test_get_entries_by_topic(fresh_memory_bank):
    bank = fresh_memory_bank
    bank.add_entry(topic="A", issue_description="d", issue_tags=[], correction_plan="c")
    bank.add_entry(topic="B", issue_description="d", issue_tags=[], correction_plan="c")
    bank.add_entry(topic="A", issue_description="d2", issue_tags=[], correction_plan="c")

    results = bank.get_entries_by_topic("A", limit=10)
    assert len(results) == 2


def test_get_entries_by_tags(fresh_memory_bank):
    bank = fresh_memory_bank
    bank.add_entry(topic="T1", issue_description="d", issue_tags=["语法"], correction_plan="c")
    bank.add_entry(topic="T2", issue_description="d", issue_tags=["风格"], correction_plan="c")

    results = bank.get_entries_by_tags(["语法"], limit=10)
    assert len(results) == 1


def test_mark_avoided(fresh_memory_bank):
    bank = fresh_memory_bank
    eid = bank.add_entry(topic="T", issue_description="d", issue_tags=[], correction_plan="c")
    assert bank.mark_avoided(eid) is True

    entries = bank.get_recent_entries(limit=10)
    assert entries[0]["is_avoided"] is True


def test_delete_entry(fresh_memory_bank):
    bank = fresh_memory_bank
    eid = bank.add_entry(topic="T", issue_description="d", issue_tags=[], correction_plan="c")
    assert bank.delete_entry(eid) is True
    assert bank.delete_entry(eid) is False
    assert bank.get_entry_count() == 0


def test_counts(fresh_memory_bank):
    bank = fresh_memory_bank
    e1 = bank.add_entry(topic="T1", issue_description="d", issue_tags=[], correction_plan="c")
    bank.add_entry(topic="T2", issue_description="d", issue_tags=[], correction_plan="c")
    assert bank.get_entry_count() == 2
    assert bank.get_pending_count() == 2

    bank.mark_avoided(e1)
    assert bank.get_pending_count() == 1


def test_format_memories_for_prompt(fresh_memory_bank):
    bank = fresh_memory_bank
    bank.add_entry(
        topic="测试",
        issue_description="问题",
        issue_tags=["标签1"],
        correction_plan="修正",
    )
    text = bank.format_memories_for_prompt(topic="测试")
    assert "历史修改意见" in text
    assert "测试" in text
    assert "问题" in text
    assert "修正" in text


def test_format_memories_empty(fresh_memory_bank):
    bank = fresh_memory_bank
    text = bank.format_memories_for_prompt()
    assert text == "【暂无历史修改意见】"


def test_generate_report(fresh_memory_bank):
    bank = fresh_memory_bank
    bank.add_entry(topic="A", issue_description="d", issue_tags=["语法"], correction_plan="c")
    bank.add_entry(topic="B", issue_description="d", issue_tags=["风格"], correction_plan="c")

    report = bank.generate_report()
    assert "总条目数: 2" in report

"""
MemoryRepository 单元测试
验证 CRUD、统计、报告等基础数据访问能力。
"""
import pytest
from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.repositories.memory_repository import MemoryRepository


@pytest.fixture
def repo():
    session = get_session()
    r = MemoryRepository(session)
    # 清理现有数据，保证测试隔离
    for e in session.query(r.model).all():
        session.delete(e)
    session.commit()
    yield r
    session.close()


def test_add_entry(repo):
    entry = repo.add_entry(
        topic="测试主题",
        issue_description="描述",
        issue_tags=["tag1", "tag2"],
        correction_plan="修正方案",
        original_text="原文",
    )
    assert entry.id
    assert entry.topic == "测试主题"
    assert entry.issue_tags == ["tag1", "tag2"]
    assert entry.is_avoided is False


def test_get_entries_by_topic(repo):
    repo.add_entry(topic="A", issue_description="d", issue_tags=[], correction_plan="c")
    repo.add_entry(topic="B", issue_description="d", issue_tags=[], correction_plan="c")
    repo.add_entry(topic="A", issue_description="d2", issue_tags=[], correction_plan="c")

    results = repo.get_entries_by_topic("A", limit=10)
    assert len(results) == 2
    assert all(e.topic == "A" for e in results)


def test_get_entries_by_tags(repo):
    repo.add_entry(topic="T1", issue_description="d", issue_tags=["语法"], correction_plan="c")
    repo.add_entry(topic="T2", issue_description="d", issue_tags=["风格"], correction_plan="c")
    repo.add_entry(topic="T3", issue_description="d", issue_tags=["语法", "风格"], correction_plan="c")

    results = repo.get_entries_by_tags(["语法"], limit=10)
    assert len(results) == 2

    results = repo.get_entries_by_tags(["语法", "风格"], limit=10)
    assert len(results) == 3


def test_get_recent_entries(repo):
    import time
    repo.add_entry(topic="Old", issue_description="d", issue_tags=[], correction_plan="c")
    time.sleep(0.01)
    repo.add_entry(topic="New", issue_description="d", issue_tags=[], correction_plan="c")

    results = repo.get_recent_entries(limit=10)
    assert results[0].topic == "New"


def test_mark_avoided(repo):
    entry = repo.add_entry(topic="T", issue_description="d", issue_tags=[], correction_plan="c")
    assert repo.mark_avoided(entry.id) is True
    refreshed = repo.get_by_id(entry.id)
    assert refreshed.is_avoided is True
    assert repo.mark_avoided("nonexistent") is False


def test_delete(repo):
    entry = repo.add_entry(topic="T", issue_description="d", issue_tags=[], correction_plan="c")
    assert repo.delete(entry.id) is True
    assert repo.get_by_id(entry.id) is None
    assert repo.delete("nonexistent") is False


def test_count_and_count_pending(repo):
    e1 = repo.add_entry(topic="T1", issue_description="d", issue_tags=[], correction_plan="c")
    repo.add_entry(topic="T2", issue_description="d", issue_tags=[], correction_plan="c")
    assert repo.count() == 2
    assert repo.count_pending() == 2

    repo.mark_avoided(e1.id)
    assert repo.count() == 2
    assert repo.count_pending() == 1


def test_generate_report(repo):
    repo.add_entry(topic="A", issue_description="d", issue_tags=["语法"], correction_plan="c")
    repo.add_entry(topic="A", issue_description="d", issue_tags=["风格"], correction_plan="c")
    repo.add_entry(topic="B", issue_description="d", issue_tags=["语法"], correction_plan="c")

    report = repo.generate_report()
    assert "总条目数: 3" in report
    assert "语法: 2条" in report
    assert "A: 2条" in report

"""测试：commit 成功后数据持久化。"""

from __future__ import annotations

import pytest

from services.base.transaction_manager import TransactionManager
from vcw_copywriter.db.models import GenerationJob
from vcw_copywriter.db.session import SessionLocal


@pytest.fixture
def tx_manager():
    return TransactionManager(session_factory=SessionLocal)


class TestCommitSuccess:
    """验证正常提交后数据写入数据库。"""

    def test_single_insert_commits(self, tx_manager: TransactionManager, app):
        """单条插入，commit 后数据存在。"""
        with tx_manager.atomic() as tx:
            job = GenerationJob(id="commit-001", job_type="test", status="pending")
            tx.session.add(job)

        # 退出 atomic 后，事务已 commit
        session = SessionLocal()
        try:
            found = session.query(GenerationJob).filter_by(id="commit-001").first()
            assert found is not None
            assert found.job_type == "test"
            assert found.status == "pending"
        finally:
            session.close()

    def test_multiple_inserts_commits(self, tx_manager: TransactionManager, app):
        """多条插入，commit 后全部存在。"""
        with tx_manager.atomic() as tx:
            for i in range(3):
                job = GenerationJob(
                    id=f"multi-{i}",
                    job_type="batch",
                    status="completed",
                )
                tx.session.add(job)

        session = SessionLocal()
        try:
            count = session.query(GenerationJob).filter(
                GenerationJob.id.in_(["multi-0", "multi-1", "multi-2"])
            ).count()
            assert count == 3
        finally:
            session.close()

    def test_compensation_queue_cleared_on_success(self, tx_manager: TransactionManager, app):
        """成功时补偿队列被清空。"""
        compensations_ran = []

        with tx_manager.atomic() as tx:
            tx.on_failure(lambda: compensations_ran.append(1))
            job = GenerationJob(id="no-comp-001", job_type="test", status="ok")
            tx.session.add(job)

        assert len(compensations_ran) == 0

    def test_session_closed_after_success(self, tx_manager: TransactionManager, app):
        """成功退出后 session 被关闭。"""
        with tx_manager.atomic() as tx:
            job = GenerationJob(id="close-001", job_type="test", status="ok")
            tx.session.add(job)

        with pytest.raises(RuntimeError, match="No active transaction session"):
            _ = tx_manager.session

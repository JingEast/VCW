"""测试：异常时自动 rollback，DB 无脏数据。"""

from __future__ import annotations

import pytest

from services.base.transaction_manager import TransactionManager
from vcw_copywriter.db.models import GenerationJob
from vcw_copywriter.db.session import SessionLocal


@pytest.fixture
def tx_manager():
    return TransactionManager(session_factory=SessionLocal)


class TestRollback:
    """验证异常时自动 rollback，数据不残留。"""

    def test_rollback_on_exception(self, tx_manager: TransactionManager, app):
        """抛出异常后，已插入的数据被 rollback。"""
        with pytest.raises(ValueError, match="intentional failure"):
            with tx_manager.atomic() as tx:
                job = GenerationJob(id="rollback-001", job_type="test", status="pending")
                tx.session.add(job)
                raise ValueError("intentional failure")

        session = SessionLocal()
        try:
            found = session.query(GenerationJob).filter_by(id="rollback-001").first()
            assert found is None
        finally:
            session.close()

    def test_partial_insert_rolled_back(self, tx_manager: TransactionManager, app):
        """部分插入后异常，全部 rollback。"""
        with pytest.raises(RuntimeError, match="boom"):
            with tx_manager.atomic() as tx:
                for i in range(2):
                    job = GenerationJob(id=f"partial-{i}", job_type="batch", status="ok")
                    tx.session.add(job)
                raise RuntimeError("boom")

        session = SessionLocal()
        try:
            count = session.query(GenerationJob).filter(
                GenerationJob.id.in_(["partial-0", "partial-1"])
            ).count()
            assert count == 0
        finally:
            session.close()

    def test_compensation_runs_on_rollback(self, tx_manager: TransactionManager, app):
        """rollback 时补偿函数被调用。"""
        compensations = []

        with pytest.raises(RuntimeError, match="fail"):
            with tx_manager.atomic() as tx:
                tx.on_failure(lambda: compensations.append("comp-1"))
                tx.on_failure(lambda: compensations.append("comp-2"))
                raise RuntimeError("fail")

        # LIFO 顺序：comp-2 先执行，然后 comp-1
        assert compensations == ["comp-2", "comp-1"]

    def test_compensation_failure_logged_and_exception_propagated(self, tx_manager: TransactionManager, caplog, app):
        """补偿失败被 logging.exception 记录，原始异常仍然抛出。"""
        import logging

        def bad_undo():
            raise RuntimeError("compensation broken")

        with pytest.raises(ValueError, match="original"):
            with tx_manager.atomic() as tx:
                tx.on_failure(bad_undo)
                raise ValueError("original")

        # 检查日志中是否记录了补偿失败
        assert any("compensation failed" in record.message.lower() for record in caplog.records if record.levelno >= logging.ERROR)

"""测试：嵌套事务（SAVEPOINT）。"""

from __future__ import annotations

import pytest

from services.base.transaction_manager import TransactionManager
from vcw_copywriter.db.models import GenerationJob
from vcw_copywriter.db.session import SessionLocal


@pytest.fixture
def tx_manager():
    return TransactionManager(session_factory=SessionLocal)


class TestNestedTransaction:
    """验证嵌套事务行为。"""

    def test_nested_atomic_reuses_session(self, tx_manager: TransactionManager, app):
        """内层 atomic 传入外层 session，数据共享。"""
        with tx_manager.atomic() as outer_tx:
            outer_job = GenerationJob(id="outer-001", job_type="outer", status="ok")
            outer_tx.session.add(outer_job)

            # 内层复用同一个 session（SAVEPOINT）
            with tx_manager.atomic(session=outer_tx.session) as inner_tx:
                inner_job = GenerationJob(id="inner-001", job_type="inner", status="ok")
                inner_tx.session.add(inner_job)

        # 两者都已 commit
        session = SessionLocal()
        try:
            outer_found = session.query(GenerationJob).filter_by(id="outer-001").first()
            inner_found = session.query(GenerationJob).filter_by(id="inner-001").first()
            assert outer_found is not None
            assert inner_found is not None
        finally:
            session.close()

    def test_nested_rollback_does_not_affect_outer(self, tx_manager: TransactionManager, app):
        """内层 atomic 异常回滚 SAVEPOINT，外层不受影响。"""
        with tx_manager.atomic() as outer_tx:
            outer_job = GenerationJob(id="outer-safe", job_type="outer", status="ok")
            outer_tx.session.add(outer_job)

            # 内层复用同一个 session，但抛异常（SAVEPOINT rollback）
            with pytest.raises(RuntimeError, match="inner fail"):
                with tx_manager.atomic(session=outer_tx.session) as inner_tx:
                    inner_job = GenerationJob(id="inner-fail", job_type="inner", status="ok")
                    inner_tx.session.add(inner_job)
                    raise RuntimeError("inner fail")

            # 外层 session 仍有效，可继续操作
            outer_tx.session.add(
                GenerationJob(id="outer-safe-2", job_type="outer", status="ok")
            )

        # 外层数据提交成功，内层被回滚
        session = SessionLocal()
        try:
            assert session.query(GenerationJob).filter_by(id="outer-safe").first() is not None
            assert session.query(GenerationJob).filter_by(id="outer-safe-2").first() is not None
            assert session.query(GenerationJob).filter_by(id="inner-fail").first() is None
        finally:
            session.close()

    def test_session_not_closed_when_passed_externally(self, tx_manager: TransactionManager, app):
        """传入外部 session 时，atomic 不关闭 session。"""
        external_session = SessionLocal()
        try:
            with tx_manager.atomic(session=external_session) as tx:
                job = GenerationJob(id="ext-001", job_type="test", status="ok")
                tx.session.add(job)

            # external_session 仍然可用
            found = external_session.query(GenerationJob).filter_by(id="ext-001").first()
            assert found is not None
        finally:
            external_session.close()

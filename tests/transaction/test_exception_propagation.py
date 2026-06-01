"""测试：异常传播与补偿日志。"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from services.base.transaction_manager import TransactionManager
from vcw_copywriter.db.session import SessionLocal


@pytest.fixture
def tx_manager():
    return TransactionManager(session_factory=SessionLocal)


class TestExceptionPropagation:
    """验证异常正确传播，补偿失败被记录。"""

    def test_original_exception_propagated(self, tx_manager: TransactionManager, app):
        """原始异常被正确抛出。"""
        with pytest.raises(RuntimeError, match="original error"):
            with tx_manager.atomic():
                raise RuntimeError("original error")

    def test_compensation_failure_logged(self, tx_manager: TransactionManager, caplog, app):
        """补偿失败记录 ERROR 级别日志。"""
        def bad_undo():
            raise RuntimeError("compensation failed")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="main"):
                with tx_manager.atomic() as tx:
                    tx.on_failure(bad_undo)
                    raise ValueError("main")

        assert any(
            "compensation failed" in record.message.lower()
            for record in caplog.records
        )

    def test_multiple_compensations_all_executed_on_failure(self, tx_manager: TransactionManager, app):
        """多个补偿全部执行，即使中间有失败。"""
        executed = []

        def ok_undo():
            executed.append("ok")

        def fail_undo():
            executed.append("fail")
            raise RuntimeError("bad")

        with pytest.raises(RuntimeError, match="main"):
            with tx_manager.atomic() as tx:
                tx.on_failure(ok_undo)
                tx.on_failure(fail_undo)
                tx.on_failure(ok_undo)
                raise RuntimeError("main")

        # LIFO: ok, fail, ok → 执行顺序: ok(3rd), fail(2nd), ok(1st)
        assert executed == ["ok", "fail", "ok"]

    def test_no_session_property_outside_atomic(self, tx_manager: TransactionManager, app):
        """不在 atomic 块内访问 session 抛出 RuntimeError。"""
        with pytest.raises(RuntimeError, match="No active transaction session"):
            _ = tx_manager.session

    def test_traceback_preserved(self, tx_manager: TransactionManager, app):
        """异常 traceback 被保留。"""
        import traceback

        try:
            with tx_manager.atomic():
                raise ValueError("with traceback")
        except ValueError as exc:
            tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            assert "with traceback" in tb_str
            assert "test_exception_propagation.py" in tb_str

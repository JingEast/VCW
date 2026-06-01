"""
统一事务管理器
================

接入真实的 SQLAlchemy 数据库事务：
  - session.begin() / commit / rollback
  - 嵌套事务支持（savepoint）
  - 补偿机制保留，但补偿失败不再静默吞异常

设计原则：
  - 所有需要原子性的 Service 操作通过 atomic() 上下文管理。
  - 非数据库操作通过 on_failure() 注册补偿函数。
  - Routes 层不允许自行处理事务。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Callable, Generator, List, Optional

from sqlalchemy.orm import Session

from vcw_copywriter.db.session import get_session

logger = logging.getLogger(__name__)


class TransactionManager:
    """统一事务管理器。

    提供 atomic() 上下文管理器，支持：
      - 正常完成时自动 commit。
      - 异常时自动 rollback，然后按 LIFO 执行补偿。
      - 补偿失败 logging.exception，不吞异常。
      - 支持嵌套事务（通过同一个 session 复用或 savepoint）。
    """

    def __init__(self, session_factory: Callable[[], Session] = get_session) -> None:
        self._session_factory = session_factory
        self._compensations: List[Callable[[], None]] = []
        self._session: Optional[Session] = None

    @contextmanager
    def atomic(
        self,
        session: Optional[Session] = None,
    ) -> Generator["TransactionManager", None, None]:
        """真实数据库事务上下文管理器。

        Args:
            session: 可选外部 session。传入时不会关闭 session；
                     未传入时内部创建并自动关闭。

        Yields:
            self: 事务管理器实例，允许在块内注册补偿操作。
        """
        previous_compensations = self._compensations
        self._compensations = []
        own_session = session is None
        if own_session:
            session = self._session_factory()
        previous_session = self._session
        self._session = session

        try:
            if own_session:
                with session.begin():
                    yield self
                    # 成功：事务已自动 commit
                    self._compensations.clear()
            else:
                # 嵌套事务：使用 SAVEPOINT，不影响外层事务
                with session.begin_nested():
                    yield self
                    self._compensations.clear()
        except Exception:
            # session.begin() / begin_nested() 已自动 rollback
            self._run_compensations()
            raise
        finally:
            if own_session and session is not None:
                session.close()
            self._session = previous_session
            self._compensations = previous_compensations

    def _run_compensations(self) -> None:
        """按 LIFO 顺序执行补偿操作。

        补偿失败时 logging.exception，不再静默吞异常。
        """
        for undo in reversed(self._compensations):
            try:
                undo()
            except Exception:
                logger.exception("Transaction compensation failed")
        self._compensations.clear()

    def on_failure(self, undo_fn: Callable[[], None]) -> None:
        """注册补偿操作（用于文件系统等非数据库操作）。

        Args:
            undo_fn: 无参可调用对象，在事务回滚时执行。
        """
        self._compensations.append(undo_fn)

    @property
    def session(self) -> Session:
        """获取当前事务中的 SQLAlchemy Session。

        Raises:
            RuntimeError: 当前不在事务上下文中。
        """
        if self._session is None:
            raise RuntimeError(
                "No active transaction session. "
                "Ensure this call is inside an atomic() block."
            )
        return self._session

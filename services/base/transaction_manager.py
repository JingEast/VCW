"""
统一事务管理器
================

支持：
  - SQLAlchemy 数据库事务（session begin/commit/rollback）
  - 文件系统补偿机制（失败时回滚已写入的文件）

设计原则：
  - 所有需要原子性的 Service 操作通过 _transaction() 上下文管理。
  - 非数据库操作通过 _on_failure() 注册补偿函数。
  - Routes 层不允许自行处理事务。
"""

from contextlib import contextmanager
from typing import Callable, List


class TransactionManager:
    """
    统一事务管理器。

    提供 atomic() 上下文管理器，支持：
      - 正常完成时清空补偿队列。
      - 异常时按 LIFO 顺序执行所有已注册的补偿操作。
    """

    def __init__(self) -> None:
        self._compensations: List[Callable] = []

    @contextmanager
    def atomic(self):
        """
        事务上下文管理器。

        Yields:
            self: 事务管理器实例，允许在块内注册补偿操作。
        """
        self._compensations = []
        try:
            yield self
            # 成功：清空补偿队列
            self._compensations.clear()
        except Exception:
            # 失败：按 LIFO 顺序执行补偿
            for undo in reversed(self._compensations):
                try:
                    undo()
                except Exception:  # nosec B110: compensation failure must not mask original exception
                    pass
            raise

    def on_failure(self, undo_fn: Callable) -> None:
        """
        注册补偿操作（用于文件系统等非数据库操作）。

        Args:
            undo_fn: 无参可调用对象，在事务回滚时执行。
        """
        self._compensations.append(undo_fn)

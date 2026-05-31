"""
Service 抽象基类
================

所有 Service 必须继承 BaseService，以获得：
  - 统一依赖入口（config）
  - 事务上下文管理（_transaction）
  - 权限检查钩子（_require_permission）
  - 补偿操作注册（_on_failure）
"""

import logging
from contextlib import contextmanager
from typing import Any, Callable, Optional

from services.base.permission_manager import PermissionManager, PermissionDenied
from services.base.transaction_manager import TransactionManager


class BaseService:
    """
    Service 层抽象基类。

    子类应在 __init__ 中调用 super().__init__(config, tm, pm)，
    并在业务方法中通过 self._require_permission() 和 self._transaction()
    统一处理权限与事务。
    """

    def __init__(
        self,
        config: Any,
        transaction_manager: Optional[TransactionManager] = None,
        permission_manager: Optional[PermissionManager] = None,
    ) -> None:
        self.config = config
        self._tm = transaction_manager
        self._pm = permission_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def _require_permission(self, action: str, **context) -> None:
        """
        检查操作权限。

        Args:
            action: 操作标识。

        Raises:
            PermissionDenied: 由 PermissionManager 抛出（默认）。
            子类可通过覆盖 _on_permission_denied 转换为专属异常。
        """
        if self._pm:
            try:
                self._pm.check(action, **context)
            except PermissionDenied as exc:
                self._on_permission_denied(exc)

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        """权限拒绝时的回调钩子，子类可覆盖以转换为专属异常。"""
        raise exc

    @contextmanager
    def _transaction(self):
        """
        事务上下文管理器。

        Yields:
            TransactionManager 实例（或 None，如果未注入）。
        """
        if self._tm:
            with self._tm.atomic() as tm:
                yield tm
        else:
            yield None

    def _on_failure(self, undo_fn: Callable) -> None:
        """
        在当前事务中注册补偿操作。

        Args:
            undo_fn: 失败时执行的补偿函数。
        """
        if self._tm:
            self._tm.on_failure(undo_fn)

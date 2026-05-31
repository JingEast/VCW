"""
历史记录服务层
==============

统管生成历史文件的查询与首页数据看板统计。
"""

import logging
from typing import Any, Dict, List, Optional

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.generation.domain.repository import ICopyRepository

logger = logging.getLogger(__name__)


class HistoryError(Exception):
    """历史记录业务异常"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class HistoryService(BaseService):
    """
    生成历史与数据看板服务。

    负责从 output_dir 扫描生成的 Markdown 文件，
    提供最近文件列表和首页统计信息。
    """

    def __init__(
        self,
        config,
        copy_repo: ICopyRepository,
        transaction_manager=None,
        permission_manager=None,
    ) -> None:
        super().__init__(config, transaction_manager, permission_manager)
        self.copy_repo = copy_repo

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        raise HistoryError(exc.message, code=exc.code)

    def _get_output_dir(self) -> str:
        return self.config.get("output", "save_dir", default="data/generated")

    def list_recent_files(self, limit: int = 5) -> List[Dict]:
        logger.debug("获取最近 %d 条生成文件", limit)
        return self.copy_repo.find_recent(limit, self._get_output_dir())

    def get_dashboard_stats(self) -> Dict[str, Any]:
        logger.debug("获取数据看板统计")
        return self.copy_repo.get_stats(self._get_output_dir())

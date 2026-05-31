"""
统一权限管理器
================

当前实现：API Key 白名单校验（替代原来分散在各 Service 中的 _check_api_key）
未来可扩展：用户角色、操作配额、IP 白名单等
"""

from typing import Optional


class PermissionDenied(Exception):
    """权限不足异常"""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(message)


class PermissionManager:
    """
    统一权限管理器。

    职责：
      - 集中管理所有操作权限判断逻辑。
      - 当前仅检查 LLM API Key；后续可扩展为用户认证、角色、配额等。
    """

    # 需要 API Key 的操作白名单
    API_KEY_ACTIONS = {
        "generate",
        "generate_stream",
        "generate_batch",
        "editor.optimize",
        "batch.generate",
    }

    def __init__(self, config) -> None:
        self.config = config

    def check(self, action: str, **context) -> None:
        """
        检查是否有权限执行指定操作。

        Args:
            action: 操作标识，如 "generate", "editor.optimize" 等。

        Raises:
            PermissionDenied: 权限不足时抛出，携带 code 与 message。
        """
        if action in self.API_KEY_ACTIONS:
            llm_config = self.config.get("llm") or {}
            if not llm_config.get("api_key"):
                raise PermissionDenied(
                    "API Key未设置，请先前往配置页面设置",
                    code="API_KEY_MISSING",
                )

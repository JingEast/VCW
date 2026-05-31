"""Editor domain repository interface (Port)."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


class IDraftRepository(ABC):
    """草稿持久化接口。"""

    @abstractmethod
    def save(
        self,
        original_content: str,
        topic: str,
        source_filepath: str = "",
        meta: str = "",
    ) -> str:
        """保存草稿，返回 draft_id。"""

    @abstractmethod
    def get(self, draft_id: str) -> Optional[Dict]:
        """获取单个草稿。"""

    @abstractmethod
    def list_all(self, status: Optional[str] = None) -> List[Dict]:
        """获取草稿列表。"""

    @abstractmethod
    def update_edited(
        self, draft_id: str, edited_content: str, edit_note: str
    ) -> bool:
        """更新精修内容。"""

    @abstractmethod
    def finalize(self, draft_id: str) -> bool:
        """标记为最终版本。"""

    @abstractmethod
    def get_diff(self, draft_id: str) -> Tuple[str, str]:
        """获取原始与精修的对比。"""

    @abstractmethod
    def build_de_ai_prompt(self, content: str) -> str:
        """构建去 AI 味优化提示词。"""

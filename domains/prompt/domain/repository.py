"""Prompt domain repository interfaces (Port)."""

from abc import ABC, abstractmethod
from typing import Dict


class IPromptTemplateRepository(ABC):
    """Prompt 模板持久化接口。"""

    @abstractmethod
    def save(self, system_prompt: str) -> None:
        """保存自定义 system prompt 模板。"""

    @abstractmethod
    def load(self) -> str:
        """加载已保存的模板；不存在时返回空字符串。"""


class IKnowledgeRepository(ABC):
    """知识库接口。"""

    @abstractmethod
    def get_resources(self) -> Dict:
        """获取全部资源数据。"""

    @abstractmethod
    def format_for_prompt(self, scope: str) -> str:
        """将知识库格式化为 prompt 文本。"""

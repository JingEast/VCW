"""
Generation Service Client Interface
===================================

EditorService 通过此接口委托文案生成能力，
屏蔽底层是进程内调用、HTTP、gRPC 还是 MQ 的实现细节。
"""

from abc import ABC, abstractmethod
from typing import Tuple


class IGenerationServiceClient(ABC):
    """文案生成服务客户端抽象（进程内/HTTP/gRPC/MQ 统一入口）。"""

    @abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[bool, str, str]:
        """
        调用生成服务完成一次文本生成。

        Args:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。

        Returns:
            (success, generated_text, meta_or_error)
        """

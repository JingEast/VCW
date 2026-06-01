"""
In-Process Generation Service Client
====================================

进程内适配器：将 IGenerationServiceClient 接口委托给本地的
GenerationService 实例。适用于单体部署阶段，后续可无缝替换为
HTTP/gRPC/MQ 客户端而不影响 EditorService。
"""

from typing import Tuple

from interfaces.generation_client import IGenerationServiceClient


class InProcessGenerationClient(IGenerationServiceClient):
    """进程内 GenerationService 适配器。"""

    def __init__(self, generation_service) -> None:
        self._svc = generation_service

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[bool, str, str]:
        return self._svc.generate_text(system_prompt, user_prompt)

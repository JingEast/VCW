"""LLM Gateway —— 统一调用入口（生产入口）。

从 ``llm.gateway.core`` 导出 ``LLMGateway``、``ProviderRegistry``、``GatewayConfig``，
作为生产代码的唯一导入路径，避免直接依赖内部模块。

Usage::

    from llm.gateway.llm_gateway import LLMGateway, ProviderRegistry, GatewayConfig
    from llm.adapter import OpenAIAdapter

    registry = ProviderRegistry()
    registry.register("kimi", OpenAIAdapter(api_key="..."))

    gateway = LLMGateway(config=GatewayConfig(), registry=registry)
    response = gateway.chat(
        [{"role": "user", "content": "你好"}],
        provider="kimi"
    )
"""

from __future__ import annotations

from .config import GatewayConfig
from .core import LLMGateway
from .registry import ProviderRegistry

__all__ = [
    "GatewayConfig",
    "LLMGateway",
    "ProviderRegistry",
]

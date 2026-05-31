"""Provider Adapter 工厂 —— 统一创建入口。

支持通过 provider 名称自动选择对应 adapter 类，
屏蔽底层 OpenAI / Anthropic / Gemini 差异。
"""

from __future__ import annotations

from typing import Type

from .base import BaseLLMAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter


# Provider → Adapter 类映射
_PROVIDER_MAP: dict[str, Type[BaseLLMAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    # OpenAI-compatible 别名
    "kimi": OpenAIAdapter,
    "moonshot": OpenAIAdapter,
    "deepseek": OpenAIAdapter,
    "azure": OpenAIAdapter,
    "vllm": OpenAIAdapter,
    "ollama": OpenAIAdapter,
}


def create_adapter(provider: str, **kwargs) -> BaseLLMAdapter:
    """根据 provider 名称创建对应 adapter 实例。

    Args:
        provider: provider 名称，如 "openai", "anthropic", "gemini", "kimi"。
        **kwargs: 透传给 adapter 构造函数（api_key, base_url, model 等）。

    Returns:
        BaseLLMAdapter 实例。

    Raises:
        ValueError: 不支持的 provider 名称。
    """
    provider = provider.lower().strip()
    cls = _PROVIDER_MAP.get(provider)
    if cls is None:
        raise ValueError(
            f"不支持的 provider: '{provider}'。"
            f"已支持: {list(_PROVIDER_MAP.keys())}"
        )
    return cls(provider_name=provider, **kwargs)


def list_providers() -> list[str]:
    """返回所有已支持的 provider 名称列表。"""
    return list(_PROVIDER_MAP.keys())


def register_provider(name: str, adapter_cls: Type[BaseLLMAdapter]) -> None:
    """注册自定义 provider adapter（扩展点）。

    Args:
        name: provider 名称。
        adapter_cls: 继承 BaseLLMAdapter 的类。
    """
    _PROVIDER_MAP[name.lower().strip()] = adapter_cls

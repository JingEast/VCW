"""
VCW Prompt Registry + Versioning System
========================================
Prompt 注册与版本化管理系统。

Usage:
    from vcw_copywriter.prompts import PromptRegistry, PromptComposer

    # 加载默认 Registry（含所有内置 Prompt）
    from vcw_copywriter.prompts.loader import load_default_registry
    registry = load_default_registry()

    # 组合 Prompt（legacy 模式，与重构前 100% 一致）
    composer = PromptComposer(registry, mode="legacy")
    system_prompt = composer.compose_system(memory_text="...", knowledge_text="...")
    user_prompt = composer.compose_user(topic="...", audience="...", ...)

    # 或一次生成两者
    system_prompt, user_prompt = composer.compose_full(...)

    # 切换到 modular 模式（拆分段落动态组装）
    composer = PromptComposer(registry, mode="modular")
"""
from .schemas import PromptVersion, PromptMetadata, PromptSpec
from .registry import PromptRegistry
from .composer import PromptComposer
from .loader import PromptLoader, load_default_registry

__all__ = [
    "PromptVersion",
    "PromptMetadata",
    "PromptSpec",
    "PromptRegistry",
    "PromptComposer",
    "PromptLoader",
    "load_default_registry",
]

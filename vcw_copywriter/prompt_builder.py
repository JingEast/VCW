"""
提示词构建模块（Prompt Registry 适配层）
=========================================
根据输入变量和历史记忆构建完整的System Prompt和User Prompt。

本模块为兼容层：对外接口 100% 保持不变，内部通过 PromptComposer
从 PromptRegistry 获取 Prompt 并动态组合。

如需直接使用 Registry API：
    from vcw_copywriter.prompts import PromptComposer, load_default_registry
"""
from typing import TYPE_CHECKING, Tuple

from .memory import MemoryBank

if TYPE_CHECKING:
    from .prompts import PromptComposer, PromptRegistry

# ------------------------------------------------------------------------------
# 向后兼容：直接暴露默认 Prompt 内容（与重构前完全一致）
# ------------------------------------------------------------------------------
# 这些变量在模块加载时从 defaults 导入，确保旧代码直接引用时行为不变。
from .prompts.defaults import (
    _SYSTEM_PROMPT_V1 as SYSTEM_PROMPT_TEMPLATE,
    _SAMPLE_1, _SAMPLE_2, _SAMPLE_3, _SAMPLE_4, _SAMPLE_5,
)

__all__ = ["SYSTEM_PROMPT_TEMPLATE", "SAMPLE_COPYWRITING", "build_user_prompt", "build_full_prompts", "get_registry", "reload_prompts"]

SAMPLE_COPYWRITING = {
    "样本一": _SAMPLE_1,
    "样本二": _SAMPLE_2,
    "样本三": _SAMPLE_3,
    "样本四": _SAMPLE_4,
    "样本五": _SAMPLE_5,
}


# ------------------------------------------------------------------------------
# 内部：延迟初始化的 Composer（避免模块加载时循环导入）
# ------------------------------------------------------------------------------
_composer = None


def _get_composer() -> "PromptComposer":
    """获取（或创建）全局 PromptComposer 实例"""
    global _composer
    if _composer is None:
        from .prompts import PromptComposer, load_default_registry
        registry = load_default_registry()
        _composer = PromptComposer(registry, mode="legacy")
    return _composer


# ------------------------------------------------------------------------------
# 公共 API（接口签名与重构前完全一致）
# ------------------------------------------------------------------------------
def build_user_prompt(
    topic: str,
    audience: str,
    core_data: str,
    policy_points: str,
    hidden_path: str,
    call_to_action: str,
    sample_ref: str = "",
    extra_requirements: str = "",
    memory_text: str = "",
    scene: str = "",
) -> str:
    """
    构建用户输入提示词

    内部通过 PromptComposer 从 Registry 组合，默认 legacy 模式保证输出不变。
    """
    composer = _get_composer()
    return composer.compose_user(
        topic=topic,
        audience=audience,
        core_data=core_data,
        policy_points=policy_points,
        hidden_path=hidden_path,
        call_to_action=call_to_action,
        sample_ref=sample_ref,
        extra_requirements=extra_requirements,
        memory_text=memory_text,
        scene=scene,
    )


def build_full_prompts(
    memory_bank: MemoryBank,
    topic: str,
    audience: str,
    core_data: str,
    policy_points: str,
    hidden_path: str,
    call_to_action: str,
    sample_ref: str = "",
    extra_requirements: str = "",
    scene: str = "",
) -> Tuple[str, str]:
    """
    构建完整的system prompt和user prompt

    Returns:
        (system_prompt, user_prompt)
    """
    composer = _get_composer()
    return composer.compose_full(
        memory_bank=memory_bank,
        topic=topic,
        audience=audience,
        core_data=core_data,
        policy_points=policy_points,
        hidden_path=hidden_path,
        call_to_action=call_to_action,
        sample_ref=sample_ref,
        extra_requirements=extra_requirements,
        scene=scene,
    )


# ------------------------------------------------------------------------------
# 新增：面向未来的 Registry 级 API（非侵入式扩展）
# ------------------------------------------------------------------------------
def get_registry() -> "PromptRegistry":
    """获取当前全局 PromptRegistry 实例"""
    return _get_composer().registry


def reload_prompts() -> None:
    """
    重新加载 Prompt（从磁盘 templates/ 目录），用于热更新。
    会重新扫描文件系统并刷新 Registry。
    """
    global _composer
    from .prompts import PromptComposer, load_default_registry
    registry = load_default_registry()
    _composer = PromptComposer(registry, mode="legacy")

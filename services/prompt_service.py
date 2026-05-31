"""
Prompt 构建服务层
=================

统管提示词组装、预览、模板持久化与热更新。
将 routes 中分散的 prompt 构建逻辑集中到单一服务，便于统一维护和测试。
"""

import logging
from typing import Tuple

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.prompt.domain.repository import IKnowledgeRepository, IPromptTemplateRepository
from vcw_copywriter.model_router import ModelRouter
from vcw_copywriter.prompt_builder import (
    build_full_prompts,
    build_user_prompt,
    SAMPLE_COPYWRITING,
    SYSTEM_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class PromptError(Exception):
    """Prompt 业务异常"""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class PromptService(BaseService):
    """
    Prompt 构建与模板管理服务。

    负责根据用户输入参数、历史记忆和知识库，组装完整的 system prompt 与 user prompt。
    """

    def __init__(
        self,
        template_repo: IPromptTemplateRepository,
        knowledge_repo: IKnowledgeRepository,
        config,
        transaction_manager=None,
        permission_manager=None,
    ) -> None:
        super().__init__(config, transaction_manager, permission_manager)
        self.template_repo = template_repo
        self.knowledge_repo = knowledge_repo

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        """将权限拒绝转换为 PromptError，保持路由层异常契约。"""
        raise PromptError(exc.message, code=exc.code)

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def build_prompts(self, req_data: dict) -> Tuple[str, str, str]:
        logger.info("Building prompts for request")

        topic = req_data.get("topic", "").strip()
        audience = req_data.get("audience", "港宝家长").strip()
        core_data = req_data.get("core_data", "").strip()
        policy_points = req_data.get("policy_points", "").strip()
        hidden_path = req_data.get("hidden_path", "").strip()
        call_to_action = req_data.get("call_to_action", "").strip()
        sample_ref = req_data.get("sample_ref", "").strip()
        extra_requirements = req_data.get("extra_requirements", "").strip()
        scene = req_data.get("scene", "").strip()

        system_prompt, user_prompt = build_full_prompts(
            memory_bank=None,  # type: ignore[arg-type]
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
        return topic, system_prompt, user_prompt

    # ------------------------------------------------------------------
    # 预览与调试
    # ------------------------------------------------------------------

    def preview(self, data: dict) -> dict:
        logger.info("Previewing prompts")

        system_prompt = data.get("system_prompt", SYSTEM_PROMPT_TEMPLATE)
        topic = data.get("topic", "DSE考砸后的保底路径")
        audience = data.get("audience", "港宝家长")
        core_data = data.get("core_data", "DSE 2025年报考人数约5万人")
        policy_points = data.get("policy_points", "副学士六科全2分可读")
        hidden_path = data.get("hidden_path", "英国部分大学接受DSE英文2分")
        call_to_action = data.get("call_to_action", "留言领取升学路径全图")

        memory_text = ""  # preview 不依赖实时记忆库
        knowledge_text = self.knowledge_repo.format_for_prompt("all")

        rendered_system = system_prompt.format(
            memory_section=memory_text,
            knowledge_section=knowledge_text,
        )

        user_prompt = build_user_prompt(
            topic=topic,
            audience=audience,
            core_data=core_data,
            policy_points=policy_points,
            hidden_path=hidden_path,
            call_to_action=call_to_action,
        )

        return {
            "system_length": len(rendered_system),
            "user_length": len(user_prompt),
            "system_preview": rendered_system[:2000]
            + ("..." if len(rendered_system) > 2000 else ""),
            "user_preview": user_prompt[:2000]
            + ("..." if len(user_prompt) > 2000 else ""),
        }

    # ------------------------------------------------------------------
    # 模板管理
    # ------------------------------------------------------------------

    def save_system_template(self, system_prompt: str) -> None:
        logger.info("Saving system template")
        self.template_repo.save(system_prompt)

        import vcw_copywriter.prompt_builder as prompt_builder

        prompt_builder.SYSTEM_PROMPT_TEMPLATE = system_prompt

    # ------------------------------------------------------------------
    # 页面上下文
    # ------------------------------------------------------------------

    def get_template_context(self) -> dict:
        logger.info("Getting template context")
        return {
            "system_template": SYSTEM_PROMPT_TEMPLATE,
            "user_template_func": build_user_prompt.__doc__ or "",
            "samples": list(SAMPLE_COPYWRITING.keys()),
        }

    def get_resources_context(self) -> dict:
        logger.info("Getting resources context")
        return self.knowledge_repo.get_resources()

    # ------------------------------------------------------------------
    # 模型状态
    # ------------------------------------------------------------------

    def get_model_status(self) -> dict:
        logger.info("Getting model status")

        llm_config = self.config.get("llm")
        endpoints = llm_config.get("endpoints")
        if not endpoints:
            return {"endpoints": [], "mode": "single"}

        router = ModelRouter(llm_config)
        return {
            "endpoints": router.get_status(),
            "mode": "multi",
        }

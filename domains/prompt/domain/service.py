"""
Prompt Domain — Domain Service
==============================

Prompt 工程领域的无状态业务逻辑服务。
"""

from typing import List

from .entity import PromptTemplate
from .value_object import PromptContext, RenderedPrompt


class PromptComposer:
    """
    Prompt 组装器（领域服务）。

    根据上下文组装完整的 system prompt 和 user prompt。
    无外部依赖，纯字符串处理。
    """

    def compose(
        self,
        template: PromptTemplate,
        context: PromptContext,
    ) -> RenderedPrompt:
        """
        组装提示词。

        Args:
            template: Prompt 模板实体。
            context: 组装上下文。

        Returns:
            渲染后的 system + user prompt。
        """
        system = template.render(
            memory_section=context.memory_text,
            knowledge_section=context.knowledge_text,
        )
        user = self._compose_user(context)
        return RenderedPrompt(system=system, user=user)

    def _compose_user(self, context: PromptContext) -> str:
        """组装 user prompt。"""
        parts = [
            f"主题：{context.topic}",
            f"受众：{context.audience}",
        ]

        if context.core_data:
            parts.append(f"核心数据：{context.core_data}")
        if context.policy_points:
            parts.append(f"政策要点：{context.policy_points}")
        if context.hidden_path:
            parts.append(f"隐藏路径/信息差：{context.hidden_path}")
        if context.call_to_action:
            parts.append(f"行动号召：{context.call_to_action}")
        if context.sample_ref:
            parts.append(f"参考样本：{context.sample_ref}")
        if context.extra_requirements:
            parts.append(f"额外要求：{context.extra_requirements}")
        if context.scene:
            parts.append(f"场景：{context.scene}")

        return "\n".join(parts)


class TemplateValidator:
    """
    模板验证器（领域服务）。

    验证 PromptTemplate 的完整性和合法性。
    """

    REQUIRED_PLACEHOLDERS = {"memory_section", "knowledge_section"}

    def validate(self, template: PromptTemplate) -> List[str]:
        """
        验证模板。

        Returns:
            错误信息列表（空列表表示验证通过）。
        """
        errors = []

        if not template.system_template or not template.system_template.strip():
            errors.append("System template cannot be empty")

        placeholders = set(template.extract_placeholders())
        missing = self.REQUIRED_PLACEHOLDERS - placeholders
        if missing:
            errors.append(f"Missing required placeholders: {missing}")

        return errors

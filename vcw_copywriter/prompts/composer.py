"""
Prompt Composer —— 动态组合引擎
---------------------------------
从 Registry 中检索 Prompt 片段，按策略组合为最终文本。

支持两种组合模式：
1. legacy（默认）：使用完整的内联 system/user 模板，输出与重构前 100% 一致
2. modular：使用拆分的 section/scene/style/sample 片段动态组装

两种模式共享同一套变量注入接口，确保上层调用方无感知切换。
"""
from typing import Dict, List, Optional

from .registry import PromptRegistry


class PromptComposer:
    """
    Prompt 组合器

    对外提供与原来 prompt_builder 相同的接口签名，内部通过 Registry 获取 Prompt。
    """

    def __init__(
        self,
        registry: Optional[PromptRegistry] = None,
        mode: str = "legacy",
    ):
        """
        Args:
            registry: PromptRegistry 实例；None 时自动加载默认 Registry
            mode: "legacy" | "modular"
        """
        if registry is None:
            from .loader import load_default_registry
            registry = load_default_registry()
        self.registry = registry
        self.mode = mode

    # ==================================================================
    # 核心组合接口（与 prompt_builder 接口对齐）
    # ==================================================================
    def compose_system(
        self,
        memory_text: str = "",
        knowledge_text: str = "",
        viral_text: str = "",
        scene: str = "",
    ) -> str:
        """
        组合 System Prompt

        Args:
            memory_text: 历史记忆文本
            knowledge_text: 业务知识库文本
            viral_text: 爆款规律文本（可选，为空时不注入）
            scene: 业务场景名称（modular 模式下用于选择场景片段）

        Returns:
            完整的 System Prompt 字符串
        """
        if self.mode == "legacy":
            return self._compose_system_legacy(
                memory_text=memory_text,
                knowledge_text=knowledge_text,
                viral_text=viral_text,
            )
        return self._compose_system_modular(
            memory_text=memory_text,
            knowledge_text=knowledge_text,
            viral_text=viral_text,
            scene=scene,
        )

    def compose_user(
        self,
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
        组合 User Prompt

        接口签名与原来 build_user_prompt 完全一致。
        """
        if self.mode == "legacy":
            return self._compose_user_legacy(
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
        return self._compose_user_modular(
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

    def compose_full(
        self,
        memory_bank=None,
        topic: str = "",
        audience: str = "",
        core_data: str = "",
        policy_points: str = "",
        hidden_path: str = "",
        call_to_action: str = "",
        sample_ref: str = "",
        extra_requirements: str = "",
        scene: str = "",
    ) -> tuple:
        """
        一次调用生成 (system_prompt, user_prompt)

        与原来 build_full_prompts 接口一致。
        """
        # 兼容旧版 memory_bank 对象
        memory_text = ""
        if memory_bank is not None:
            try:
                memory_text = memory_bank.format_memories_for_prompt(topic=topic)
            except Exception:
                memory_text = ""

        # 知识库文本
        knowledge_text = ""
        try:
            from ..knowledge_base import format_for_prompt
            knowledge_text = format_for_prompt("all")
        except Exception:
            knowledge_text = ""

        # 爆款规律文本（仅在 system prompt 需要时获取）
        viral_text = ""
        try:
            from ..viral_analyzer import ViralAnalyzer
            viral = ViralAnalyzer()
            viral_text = viral.format_for_prompt()
        except Exception:
            viral_text = ""

        system_prompt = self.compose_system(
            memory_text=memory_text,
            knowledge_text=knowledge_text,
            viral_text=viral_text,
            scene=scene,
        )
        user_prompt = self.compose_user(
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
        return system_prompt, user_prompt

    # ==================================================================
    # Legacy 模式 —— 与重构前输出 100% 一致
    # ==================================================================
    def _compose_system_legacy(
        self,
        memory_text: str,
        knowledge_text: str,
        viral_text: str,
    ) -> str:
        """Legacy System Prompt：使用完整的内联模板"""
        spec = self.registry.get_or_raise("system:copywriting", version="1.0.0")
        template = spec.content

        # 爆款规律增强（与 auto_prompt.build_enhanced_system_prompt 逻辑一致）
        if viral_text:
            # 在爆款规律总结章节注入 viral_text
            marker = "## 爆款规律总结（必须融入生成）"
            if marker in template:
                inject = f"{marker}\n\n{viral_text}\n\n---\n\n{marker}"
                template = template.replace(marker, inject, 1)

        return template.format(
            memory_section=memory_text or "【暂无历史修改意见】",
            knowledge_section=knowledge_text or "【暂无业务知识库内容】",
        )

    def _compose_user_legacy(
        self,
        topic: str,
        audience: str,
        core_data: str,
        policy_points: str,
        hidden_path: str,
        call_to_action: str,
        sample_ref: str,
        extra_requirements: str,
        memory_text: str,
        scene: str,
    ) -> str:
        """Legacy User Prompt：使用完整的内联模板"""
        spec = self.registry.get_or_raise("user:copywriting", version="1.0.0")
        template = spec.content

        # 样本文案映射
        samples = self._get_samples_dict()
        scene_sample_map = {
            "港籍升学规划": "样本四",
            "DSE笔试备考": "样本五",
            "港澳台联考/内地升学": "样本二",
        }
        auto_sample = sample_ref
        if not auto_sample and scene in scene_sample_map:
            auto_sample = scene_sample_map[scene]

        matched_sample = None
        for key in samples:
            if key in auto_sample:
                matched_sample = samples[key]
                break

        return template.format(
            topic=topic,
            scene=scene,
            scene_guard=(
                f"业务场景：{scene}\n【注意】请务必确保文案内容严格限定在上述业务场景内，禁止涉及其他场景的内容。"
                if scene else ""
            ),
            audience=audience,
            core_data=core_data,
            policy_points=policy_points,
            hidden_path=hidden_path,
            call_to_action=call_to_action,
            sample_section=self._build_sample_section(auto_sample, matched_sample),
            extra_section=(f"额外要求：{extra_requirements}" if extra_requirements else ""),
            memory_section=(
                f"\n## 历史修改意见\n{memory_text}"
                if memory_text and memory_text != "【暂无历史修改意见】"
                else ""
            ),
        )

    def _build_sample_section(self, sample_ref: str, matched_sample: Optional[str]) -> str:
        """构建参考样本段落"""
        if not sample_ref:
            return ""
        if matched_sample:
            lines = [
                "",
                "## 参考样本文案（必须严格模仿其断句节奏、口语化程度和结构框架）",
                f"【样本名称】{sample_ref}",
                "【样本正文】",
                matched_sample,
                "【模仿要求】",
                "1. 严格模仿上述样本的断句节奏——短句为主，每句独立成段或紧跟换行，不要写成连贯长段落",
                "2. 严格模仿口语化特征——大量使用'咱们''孩子''家长''其实''说白了'，自然停顿感",
                "3. 严格模仿数字呈现方式——'一万多人'而非'11882人'，'百分之二十'或'两成'",
                "4. 严格模仿过渡方式——用'首先''再看''另外''最后'等自然口语过渡，而非学术排比",
                "5. 严格模仿情绪节奏——焦虑→希望→具体方案→隐藏信息差→业务引导→行动号召",
            ]
            return "\n".join(lines)
        return f"参考样本：{sample_ref}"

    def _get_samples_dict(self) -> Dict[str, str]:
        """从 Registry 获取所有 sample 类型 Prompt，转为 {名称: 内容} 字典"""
        result = {}
        for spec in self.registry.list_by_type("sample"):
            # id 格式为 "sample:样本一" -> 取后半部分作为键
            name = spec.id.rsplit(":", 1)[-1]
            result[name] = spec.content
        return result

    # ==================================================================
    # Modular 模式 —— 拆分段落动态组装（供未来扩展）
    # ==================================================================
    def _compose_system_modular(
        self,
        memory_text: str,
        knowledge_text: str,
        viral_text: str,
        scene: str,
    ) -> str:
        """
        Modular System Prompt：从 section / scene / style 片段组装
        当前为骨架实现，未来可在此基础上增加更细粒度的组合逻辑。
        """
        parts: List[str] = []

        # 1. 角色设定
        role = self.registry.get("section:role")
        if role:
            parts.append(role.content)

        # 2. 核心任务
        task = self.registry.get("section:task")
        if task:
            parts.append(task.content)

        # 3. 文案结构
        structure = self.registry.get("section:structure")
        if structure:
            parts.append(structure.content)

        # 4. 场景边界（若指定了 scene）
        if scene:
            scene_spec = self.registry.get(f"scene:{self._scene_key(scene)}")
            if scene_spec:
                parts.append(scene_spec.content)

        # 5. 语言风格
        style = self.registry.get("section:style")
        if style:
            parts.append(style.content)

        # 6. 爆款规律
        viral = self.registry.get("section:viral")
        if viral:
            content = viral.content
            if viral_text:
                marker = "## 爆款规律总结（必须融入生成）"
                if marker in content:
                    content = content.replace(
                        marker,
                        f"{marker}\n\n{viral_text}\n\n---\n\n{marker}",
                        1,
                    )
            parts.append(content)

        # 7. 迭代优化与记忆
        parts.append(f"## 迭代优化与记忆机制（核心新增）\n\n{memory_text or '【暂无历史修改意见】'}")

        # 8. 信息时效性
        timeliness = self.registry.get("section:timeliness")
        if timeliness:
            parts.append(timeliness.content)

        # 9. 业务知识库
        parts.append(f"## 业务知识库（生成文案时必须参考）\n\n{knowledge_text or '【暂无业务知识库内容】'}")

        # 10. 质量控制
        quality = self.registry.get("section:quality")
        if quality:
            parts.append(quality.content)

        return "\n\n---\n\n".join(parts)

    def _compose_user_modular(
        self,
        topic: str,
        audience: str,
        core_data: str,
        policy_points: str,
        hidden_path: str,
        call_to_action: str,
        sample_ref: str,
        extra_requirements: str,
        memory_text: str,
        scene: str,
    ) -> str:
        """
        Modular User Prompt：动态组装用户输入部分
        """
        # 当前实现回退到 legacy 模板，因为 user prompt 的结构相对固定
        # 未来可拆分为：input_variables / sample_reference / execution_instructions
        return self._compose_user_legacy(
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

    @staticmethod
    def _scene_key(scene_name: str) -> str:
        """将场景中文名转换为 registry ID 键"""
        mapping = {
            "香港中小学插班规划": "insertion",
            "DSE笔试备考": "dse",
            "港籍升学规划": "admission",
            "港澳台联考/内地升学": "joint",
            "海外升学": "overseas",
        }
        return mapping.get(scene_name, scene_name)

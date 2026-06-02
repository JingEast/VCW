"""
文案生成服务层
==============

统管单次生成、流式生成、批量生成、质量检查、结果持久化
以及异步任务队列的提交与查询。

职责边界：
  - 接收原始请求数据（dict），负责完整业务编排。
  - 调用 vcw_copywriter 核心模块完成 AI 生成，不直接处理 HTTP。
  - 管理业务异常，统一抛出 GenerationError，由 routes 层转换为 HTTP 响应。
"""

from pathlib import Path
from typing import Dict, List, Tuple, Iterator, Optional, Callable

from typing import TYPE_CHECKING

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.generation.domain.repository import (
    ICopyRepository,
    IMemoryRepository,
)
from domains.editor.domain.repository import IDraftRepository
from vcw_copywriter.prompt_builder import build_full_prompts
from vcw_copywriter.checker import check_and_report
from vcw_copywriter.batch_generator import BatchGenerator
from app.core.profiler import profile

if TYPE_CHECKING:
    from llm.gateway.llm_gateway import LLMGateway


class GenerationError(Exception):
    """文案生成过程中的业务异常"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class GenerationService(BaseService):
    """
    文案生成服务。

    负责协调 Prompt → LLM 调用 → 质量检查 → 保存/创建草稿的完整工作流。
    继承 BaseService，统一通过 _require_permission / _transaction 处理权限与事务。
    """

    def __init__(
        self,
        config,
        copy_repo: ICopyRepository,
        memory_repo: IMemoryRepository,
        draft_repo: IDraftRepository,
        transaction_manager=None,
        permission_manager=None,
        llm_gateway: Optional["LLMGateway"] = None,
    ) -> None:
        """
        Args:
            config: Config 实例。
            copy_repo: ICopyRepository 实例（文案持久化）。
            memory_repo: IMemoryRepository 实例（记忆库）。
            draft_repo: IDraftRepository 实例（草稿持久化）。
            transaction_manager: 事务管理器（可选）。
            permission_manager: 权限管理器（可选）。
            llm_gateway: LLMGateway 实例（推荐，接入统一 adapter 层）。
        """
        super().__init__(config, transaction_manager, permission_manager)
        self.copy_repo = copy_repo
        self.memory_repo = memory_repo
        self.draft_repo = draft_repo
        self.llm_gateway = llm_gateway

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        """将权限拒绝转换为 GenerationError，保持路由层异常契约。"""
        raise GenerationError(exc.message, code=exc.code)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _get_llm_config(self) -> Dict:
        return self.config.get("llm") or {}

    def _build_prompts(self, req_data: Dict) -> Tuple[str, str, str]:
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
            memory_bank=self.memory_repo,  # type: ignore[arg-type]
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

        # 批量子任务支持：注入角度提示词
        angle = req_data.get("angle")
        if angle:
            from vcw_copywriter.batch_generator import ANGLE_PRESETS
            preset = ANGLE_PRESETS.get(angle, {})
            style_note = preset.get("style_note", "")
            if style_note:
                angle_section = (
                    f"\n\n---\n\n## 本次生成角度要求\n\n"
                    f"【角度类型】{angle}\n"
                    f"【风格要求】{style_note}\n\n"
                    f"请确保本次生成的文案严格符合上述角度风格，与其他角度有明显差异。\n"
                )
                user_prompt += angle_section

        return topic, system_prompt, user_prompt

    def _do_generate(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        if self.llm_gateway is not None:
            return self._do_generate_via_gateway(system_prompt, user_prompt)
        # 向后兼容：未注入 gateway 时回退到旧实现（已标记 deprecated）
        from vcw_copywriter.model_router import ModelRouter
        from vcw_copywriter.generator import CopywriterGenerator

        llm_config = self._get_llm_config()
        endpoints = llm_config.get("endpoints")
        if endpoints:
            router = ModelRouter(llm_config)
            success, content, meta = router.generate(
                system_prompt,
                user_prompt,
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 2000),
            )
        else:
            generator = CopywriterGenerator(llm_config)
            success, content, meta = generator.generate(system_prompt, user_prompt)
        return success, content, meta

    def _do_generate_via_gateway(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        """通过 LLMGateway 生成文案（新路径）。"""
        llm_config = self._get_llm_config()
        try:
            response = self.llm_gateway.complete(  # type: ignore[union-attr]
                prompt=user_prompt,
                system=system_prompt,
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 2000),
            )
        except Exception as exc:
            return False, "", f"生成失败: {exc}"

        meta = (
            f"模型: {response.model} | "
            f"Provider: {response.provider} | "
            f"Tokens: {response.usage.total_tokens}"
        )
        return True, response.content, meta

    def generate_text(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        """
        通用 LLM 文本生成入口，供其他 Service 委托调用。
        """
        self._require_permission("generate")
        return self._do_generate(system_prompt, user_prompt)

    # ------------------------------------------------------------------
    # 单次生成
    # ------------------------------------------------------------------

    @profile(name="generation_service._generate_copy_internal")
    def _generate_copy_internal(
        self,
        req_data: Dict,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict:
        """
        核心文案生成逻辑（不含权限检查）。
        供 Celery Worker 在后台调用。
        """
        if on_progress:
            on_progress(5, "正在构建提示词...")
        topic, system_prompt, user_prompt = self._build_prompts(req_data)

        if on_progress:
            on_progress(20, "正在调用AI生成...")
        success, content, meta = self._do_generate(system_prompt, user_prompt)
        if not success:
            raise GenerationError(
                f"生成失败: {meta}",
                code="GENERATION_FAILED",
                details={"meta": meta},
            )

        if on_progress:
            on_progress(70, "正在进行质量检查...")
        strict_mode = self.config.get("quality_check", "strict_mode", default=False)
        passed, report = check_and_report(content, strict_mode)

        if on_progress:
            on_progress(90, "正在保存结果...")

        with self._transaction():
            output_dir = self.config.get("output", "save_dir", default="data/generated")
            filepath = self.copy_repo.save(content, topic, meta, output_dir)
            self._on_failure(lambda fp=filepath: Path(fp).unlink(missing_ok=True))

            draft_id = self.draft_repo.save(
                original_content=content,
                topic=topic,
                source_filepath=filepath,
                meta=str(meta) if meta else "",
            )

        if on_progress:
            on_progress(100, "生成完成")

        issues = []
        for line in report.split("\n"):
            line = line.strip()
            if line.startswith("[ERR]"):
                issues.append({"level": "error", "text": line.replace("[ERR]", "").strip()})
            elif line.startswith("[WARN]"):
                issues.append({"level": "warning", "text": line.replace("[WARN]", "").strip()})
            elif line.startswith("[INFO]"):
                issues.append({"level": "info", "text": line.replace("[INFO]", "").strip()})

        return {
            "topic": topic,
            "content": content,
            "meta": meta,
            "filepath": filepath,
            "passed": passed,
            "issues": issues,
            "report": report,
            "draft_id": draft_id,
        }

    def generate_copy(
        self,
        req_data: Dict,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict:
        self._require_permission("generate")
        return self._generate_copy_internal(req_data, on_progress=on_progress)

    def generate_stream(self, req_data: Dict) -> Iterator[Tuple[str, str]]:
        self._require_permission("generate_stream")

        topic, system_prompt, user_prompt = self._build_prompts(req_data)

        if self.llm_gateway is not None:
            yield from self._generate_stream_via_gateway(system_prompt, user_prompt)
            return

        # 向后兼容
        from vcw_copywriter.model_router import ModelRouter
        from vcw_copywriter.generator import CopywriterGenerator

        llm_config = self._get_llm_config()
        endpoints = llm_config.get("endpoints")
        if endpoints:
            router = ModelRouter(llm_config)
            meta_sent = False
            for is_meta, text, _ in router.generate_stream(
                system_prompt,
                user_prompt,
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 2000),
            ):
                if is_meta and text.startswith("model:") and not meta_sent:
                    yield "meta", text
                    meta_sent = True
                elif is_meta and text.startswith("done"):
                    yield "done", text
                else:
                    yield "content", text
        else:
            generator = CopywriterGenerator(llm_config)
            for text in generator.generate_stream(system_prompt, user_prompt):
                if text.startswith("[错误]"):
                    yield "error", text
                    return
                yield "content", text
            yield "done", "ok"

    def _generate_stream_via_gateway(
        self, system_prompt: str, user_prompt: str
    ) -> Iterator[Tuple[str, str]]:
        """通过 LLMGateway 流式生成（新路径）。"""
        llm_config = self._get_llm_config()
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        meta_sent = False
        try:
            for chunk in self.llm_gateway.generate_stream(  # type: ignore[union-attr]
                messages,
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 2000),
            ):
                if not meta_sent:
                    yield "meta", f"model:{chunk.model}|provider:{chunk.provider}"
                    meta_sent = True
                if chunk.content:
                    yield "content", chunk.content
        except Exception as exc:
            yield "error", f"[错误] 流式生成失败: {exc}"
            return

        yield "done", "ok"

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------

    def generate_batch(self, req_data: Dict, angles: List[str]) -> List[Dict]:
        self._require_permission("generate_batch")
        topic, system_prompt, user_prompt = self._build_prompts(req_data)

        llm_config = self._get_llm_config()
        try:
            batch_gen = BatchGenerator(llm_config)
            results = batch_gen.generate_batch(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                angles=angles,
            )
            batch_gen.save_batch(results, topic)
            return results
        except GenerationError:
            raise
        except ValueError as e:
            err_msg = str(e)
            if "API Key" in err_msg:
                raise GenerationError(err_msg, code="API_KEY_MISSING")
            raise GenerationError(err_msg, code="GENERATION_FAILED")
        except Exception as e:
            raise GenerationError(f"批量生成失败: {str(e)}", code="BATCH_GENERATION_FAILED")

    # ------------------------------------------------------------------
    # 异步任务（已迁移至 AsyncTaskService）
    # ------------------------------------------------------------------

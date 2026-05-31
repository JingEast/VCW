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

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Iterator, Optional, Callable

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.generation.domain.repository import (
    ICopyRepository,
    IMemoryRepository,
    ITaskRepository,
)
from domains.editor.domain.repository import IDraftRepository
from vcw_copywriter.prompt_builder import build_full_prompts
from vcw_copywriter.generator import CopywriterGenerator
from vcw_copywriter.model_router import ModelRouter
from vcw_copywriter.checker import check_and_report
from vcw_copywriter.batch_generator import BatchGenerator


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
        task_repo: Optional[ITaskRepository] = None,
    ) -> None:
        """
        Args:
            config: Config 实例。
            copy_repo: ICopyRepository 实例（文案持久化）。
            memory_repo: IMemoryRepository 实例（记忆库）。
            draft_repo: IDraftRepository 实例（草稿持久化）。
            transaction_manager: 事务管理器（可选）。
            permission_manager: 权限管理器（可选）。
            task_repo: ITaskRepository 实例（异步任务队列，可选，向后兼容）。
        """
        super().__init__(config, transaction_manager, permission_manager)
        self.copy_repo = copy_repo
        self.task_repo = task_repo
        self.memory_repo = memory_repo
        self.draft_repo = draft_repo

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

    def generate_text(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str, str]:
        """
        通用 LLM 文本生成入口，供其他 Service 委托调用。
        """
        self._require_permission("generate")
        return self._do_generate(system_prompt, user_prompt)

    # ------------------------------------------------------------------
    # 单次生成
    # ------------------------------------------------------------------

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
    # 异步任务
    # ------------------------------------------------------------------

    def submit_async_generate(self, req_data: Dict) -> str:
        topic = req_data.get("topic", "").strip()
        if not topic:
            raise GenerationError("主题不能为空", code="MISSING_TOPIC")

        self._require_permission("generate")

        from vcw_celery_tasks.tasks import generate_copy_task
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob
        import uuid

        result = generate_copy_task.delay(req_data)
        task_id = result.id

        session = get_session()
        try:
            job = GenerationJob(
                id=str(uuid.uuid4())[:12],
                job_type="generate",
                status="pending",
                progress=0,
                message="等待执行...",
                celery_task_id=task_id,
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        return task_id

    def get_async_status(self, task_id: str) -> Optional[Dict]:
        from celery.result import AsyncResult
        from celery_app import app as celery_app
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        session = get_session()
        try:
            job = session.query(GenerationJob).filter(
                GenerationJob.celery_task_id == task_id
            ).first()
        finally:
            session.close()

        if not job:
            raise GenerationError("任务不存在", code="TASK_NOT_FOUND")

        result = AsyncResult(task_id, app=celery_app)

        _STATE_MAP = {
            "PENDING": "pending",
            "STARTED": "running",
            "PROGRESS": "running",
            "RETRY": "pending",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "REVOKED": "cancelled",
        }

        state = result.state
        status = _STATE_MAP.get(state, "pending")

        progress = 0
        message = ""
        result_data = {}
        error = ""

        if state == "PROGRESS" and isinstance(result.info, dict):
            progress = result.info.get("progress", 0)
            message = result.info.get("message", "")
        elif state == "SUCCESS":
            progress = 100
            message = "生成完成"
            result_data = result.result if isinstance(result.result, dict) else {}
        elif state == "FAILURE":
            message = "生成失败"
            error = str(result.result) if result.result else ""
        elif state == "REVOKED":
            message = "任务已取消"
        elif state == "STARTED":
            message = "正在生成..."
            progress = 10
        elif state == "RETRY":
            message = "任务正在重试..."
        else:
            message = "等待执行..."

        completed_at = None
        if result.date_done:
            completed_at = result.date_done.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "id": task_id,
            "type": "generate",
            "status": status,
            "progress": progress,
            "message": message,
            "result": result_data,
            "error": error,
            "created_at": "",
            "started_at": "",
            "completed_at": completed_at or "",
        }

    def cancel_async_task(self, task_id: str) -> bool:
        from celery_app import app as celery_app

        celery_app.control.revoke(task_id, terminate=True)
        return True

    # ------------------------------------------------------------------
    # 异步批量任务
    # ------------------------------------------------------------------

    def submit_async_batch(self, req_data: Dict, angles: List[str]) -> str:
        topic = req_data.get("topic", "").strip()
        if not topic:
            raise GenerationError("主题不能为空", code="MISSING_TOPIC")
        if not angles:
            raise GenerationError("角度列表不能为空", code="MISSING_ANGLES")

        self._require_permission("generate_batch")

        from vcw_celery_tasks.tasks import generate_batch_task
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob
        import uuid

        batch_id = str(uuid.uuid4())[:12]

        session = get_session()
        try:
            job = GenerationJob(
                id=batch_id,
                job_type="batch",
                status="pending",
                progress=0,
                message=f"等待执行... 共 {len(angles)} 个角度",
                result={"total": len(angles), "completed": 0, "failed": 0, "cancelled": 0},
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        generate_batch_task.delay(req_data, angles, batch_id=batch_id)
        return batch_id

    def get_async_batch_status(self, batch_id: str) -> Optional[Dict]:
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        session = get_session()
        try:
            parent = session.query(GenerationJob).filter(
                GenerationJob.id == batch_id,
                GenerationJob.job_type == "batch",
            ).first()

            if not parent:
                raise GenerationError("批次不存在", code="BATCH_NOT_FOUND")

            children = session.query(GenerationJob).filter(
                GenerationJob.parent_batch_id == batch_id,
            ).all()
        finally:
            session.close()

        total = len(children)
        completed = sum(1 for c in children if c.status == "completed")
        failed = sum(1 for c in children if c.status == "failed")
        cancelled = sum(1 for c in children if c.status == "cancelled")
        pending = total - completed - failed - cancelled

        status = parent.status
        if status not in ("completed", "failed", "cancelled", "partial"):
            if pending == total:
                status = "pending"
            elif pending > 0:
                status = "running"
            else:
                if failed == 0 and cancelled == 0:
                    status = "completed"
                elif completed > 0:
                    status = "partial"
                elif cancelled > 0:
                    status = "cancelled"
                else:
                    status = "failed"

        progress = int((completed + failed + cancelled) / total * 100) if total > 0 else 0

        items = []
        for child in children:
            angle = (child.result or {}).get("angle", "") if child.result else ""
            items.append({
                "subtask_id": child.id,
                "angle": angle,
                "status": child.status,
                "result": child.result or {},
                "error": child.error or "",
            })

        def _fmt(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""

        return {
            "batch_id": batch_id,
            "status": status,
            "total": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "pending": pending,
            "progress_percent": progress,
            "items": items,
            "created_at": _fmt(parent.created_at),
            "started_at": _fmt(parent.started_at),
            "completed_at": _fmt(parent.completed_at),
            "message": f"{completed}/{total} 完成, {failed} 失败, {cancelled} 取消, {pending} 等待中",
        }

    def cancel_async_batch(self, batch_id: str) -> bool:
        from celery_app import app as celery_app
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import GenerationJob

        session = get_session()
        try:
            parent = session.query(GenerationJob).filter(
                GenerationJob.id == batch_id,
                GenerationJob.job_type == "batch",
            ).first()

            if not parent:
                raise GenerationError("批次不存在", code="BATCH_NOT_FOUND")

            children = session.query(GenerationJob).filter(
                GenerationJob.parent_batch_id == batch_id,
            ).all()

            revoked = 0
            for child in children:
                if child.status in ("pending", "running"):
                    if child.celery_task_id:
                        celery_app.control.revoke(child.celery_task_id, terminate=True)
                    child.status = "cancelled"
                    revoked += 1

            parent.status = "cancelled"
            parent.completed_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

        return True

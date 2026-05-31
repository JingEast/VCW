"""
精修编辑器服务层
================

统管草稿生命周期（创建、读取、更新、定稿、对比）
以及 AI 辅助优化（去 AI 味）等编辑器相关操作。

职责边界：
  - 接收 DTO 或裸参数，负责完整业务编排与校验。
  - 通过 IDraftRepository 完成底层草稿管理，不直接处理 HTTP。
  - 统一抛出 EditorError，由 routes 层转换为 HTTP 响应。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.editor.domain.repository import IDraftRepository


class EditorError(Exception):
    """编辑器业务异常"""

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


# ------------------------------------------------------------------------------
# Request DTOs（仅用于多字段场景）
# ------------------------------------------------------------------------------

@dataclass
class SaveDraftRequest:
    original_content: str
    topic: str
    source_filepath: str = ""
    meta: str = ""


@dataclass
class UpdateDraftRequest:
    draft_id: str
    edited_content: str
    edit_note: str = ""
    finalize: bool = False


@dataclass
class DeAIOptimizeRequest:
    content: str


# ------------------------------------------------------------------------------
# Response DTOs
# ------------------------------------------------------------------------------

@dataclass
class DraftResponse:
    draft_id: str
    topic: str
    status: str
    original: str
    edited: str
    created_at: str
    updated_at: str
    source_filepath: str = ""
    meta: str = ""
    edit_history: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> "DraftResponse":
        return cls(
            draft_id=d.get("id", ""),
            topic=d.get("topic", ""),
            status=d.get("status", ""),
            original=d.get("original", ""),
            edited=d.get("edited", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            source_filepath=d.get("source_filepath", ""),
            meta=d.get("meta", ""),
            edit_history=d.get("edit_history", []),
        )


@dataclass
class DraftListResponse:
    drafts: List[DraftResponse]
    total: int


@dataclass
class DiffResponse:
    original: str
    edited: str


@dataclass
class DeAIOptimizeResponse:
    success: bool
    optimized: str
    meta: str = ""
    error: Optional[str] = None


# ------------------------------------------------------------------------------
# EditorService
# ------------------------------------------------------------------------------

class EditorService(BaseService):
    """
    精修编辑器服务。

    作为 IDraftRepository 的门面（Facade），向上层路由提供更高阶的编辑操作接口。
    继承 BaseService，统一通过 _require_permission / _transaction 处理权限与事务。
    """

    def __init__(
        self,
        draft_repo: IDraftRepository,
        config,
        generation_service,
        transaction_manager=None,
        permission_manager=None,
    ) -> None:
        """
        Args:
            draft_repo: IDraftRepository 实例（底层草稿管理）。
            config: Config 实例。
            generation_service: GenerationService 实例（用于委托 LLM 调用）。
            transaction_manager: 事务管理器（可选）。
            permission_manager: 权限管理器（可选）。
        """
        super().__init__(config, transaction_manager, permission_manager)
        self.draft_repo = draft_repo
        self.generation_service = generation_service

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        """将权限拒绝转换为 EditorError，保持路由层异常契约。"""
        raise EditorError(exc.message, code=exc.code)

    # ------------------------------------------------------------------
    # 草稿生命周期
    # ------------------------------------------------------------------

    def load_or_create_draft(
        self,
        content: str,
        topic: str,
        angle: str,
        draft_id: str,
    ) -> DraftResponse:
        if draft_id:
            draft = self.draft_repo.get(draft_id)
            if draft:
                return DraftResponse.from_dict(draft)

        if content:
            new_id = self.draft_repo.save(
                original_content=content,
                topic=f"{topic}_{angle}" if angle else topic,
            )
            draft = self.draft_repo.get(new_id)
            if draft:
                return DraftResponse.from_dict(draft)

        return DraftResponse(
            draft_id="",
            topic=topic,
            status="draft",
            original="",
            edited="",
            created_at="",
            updated_at="",
        )

    def save_draft(self, req: SaveDraftRequest) -> str:
        if not req.original_content or not req.original_content.strip():
            raise EditorError("内容不能为空", code="EMPTY_CONTENT")
        if not req.topic or not req.topic.strip():
            raise EditorError("主题不能为空", code="EMPTY_TOPIC")

        return self.draft_repo.save(
            original_content=req.original_content,
            topic=req.topic,
            source_filepath=req.source_filepath,
            meta=req.meta,
        )

    def get_draft(self, draft_id: str) -> DraftResponse:
        if not draft_id:
            raise EditorError("草稿ID不能为空", code="MISSING_DRAFT_ID")

        draft = self.draft_repo.get(draft_id)
        if not draft:
            raise EditorError("草稿不存在", code="DRAFT_NOT_FOUND")

        return DraftResponse.from_dict(draft)

    def list_drafts(self, status: Optional[str] = None) -> DraftListResponse:
        drafts = self.draft_repo.list_all(status=status)
        return DraftListResponse(
            drafts=[DraftResponse.from_dict(d) for d in drafts],
            total=len(drafts),
        )

    def update_draft(self, req: UpdateDraftRequest) -> DraftResponse:
        if not req.draft_id:
            raise EditorError("草稿ID不能为空", code="MISSING_DRAFT_ID")

        ok = self.draft_repo.update_edited(req.draft_id, req.edited_content, req.edit_note)
        if not ok:
            raise EditorError("草稿不存在或更新失败", code="UPDATE_FAILED")

        if req.finalize:
            ok = self.draft_repo.finalize(req.draft_id)
            if not ok:
                raise EditorError("定稿失败", code="FINALIZE_FAILED")

        draft = self.draft_repo.get(req.draft_id)
        if draft is None:
            raise EditorError("草稿不存在", code="DRAFT_NOT_FOUND")
        return DraftResponse.from_dict(draft)

    def get_diff(self, draft_id: str) -> DiffResponse:
        if not draft_id:
            raise EditorError("草稿ID不能为空", code="MISSING_DRAFT_ID")

        original, edited = self.draft_repo.get_diff(draft_id)
        if not original and not edited:
            raise EditorError("草稿不存在", code="DRAFT_NOT_FOUND")

        return DiffResponse(original=original, edited=edited)

    # ------------------------------------------------------------------
    # AI 辅助优化
    # ------------------------------------------------------------------

    def build_de_ai_prompt(self, content: str) -> str:
        if not content or not content.strip():
            raise EditorError("内容不能为空", code="EMPTY_CONTENT")

        return self.draft_repo.build_de_ai_prompt(content)

    def optimize_with_ai(self, req: DeAIOptimizeRequest) -> DeAIOptimizeResponse:
        self._require_permission("editor.optimize")
        de_ai_prompt = self.build_de_ai_prompt(req.content)
        success, optimized, meta = self.generation_service.generate_text(
            system_prompt="你是一位资深短视频文案编辑。请直接输出润色后的文案，不要加任何解释。",
            user_prompt=de_ai_prompt,
        )

        if not success:
            raise EditorError(meta or "优化失败", code="GENERATION_FAILED")

        return DeAIOptimizeResponse(
            success=True,
            optimized=optimized,
            meta=meta,
        )

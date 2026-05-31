"""Editor domain application handlers."""

from typing import Optional

from services.editor_service import (
    DeAIOptimizeRequest,
    SaveDraftRequest,
    UpdateDraftRequest,
)

from .commands import DeAIOptimizeCommand, SaveDraftCommand, UpdateDraftCommand
from .queries import GetDiffQuery, GetDraftQuery, ListDraftsQuery


class EditorHandler:
    """Orchestrates editor use cases."""

    def __init__(self, editor_service):
        self._svc = editor_service

    def handle_save_draft(self, command: SaveDraftCommand) -> str:
        req = SaveDraftRequest(
            original_content=command.original_content,
            topic=command.topic,
            source_filepath=command.source_filepath,
            meta=command.meta,
        )
        return self._svc.save_draft(req)

    def handle_update_draft(self, command: UpdateDraftCommand):
        req = UpdateDraftRequest(
            draft_id=command.draft_id,
            edited_content=command.edited_content,
            edit_note=command.edit_note,
            finalize=command.finalize,
        )
        return self._svc.update_draft(req)

    def handle_get_draft(self, query: GetDraftQuery):
        return self._svc.get_draft(query.draft_id)

    def handle_list_drafts(self, query: ListDraftsQuery):
        return self._svc.list_drafts(query.status)

    def handle_get_diff(self, query: GetDiffQuery):
        return self._svc.get_diff(query.draft_id)

    def handle_de_ai_optimize(self, command: DeAIOptimizeCommand):
        req = DeAIOptimizeRequest(content=command.content)
        return self._svc.optimize_with_ai(req)

    def handle_load_or_create_draft(
        self, content: str, topic: str, angle: str = "", draft_id: str = ""
    ):
        return self._svc.load_or_create_draft(content, topic, angle, draft_id)

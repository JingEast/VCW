"""Editor domain repository implementation (Adapter)."""

from typing import Dict, List, Optional, Tuple

from domains.editor.domain.repository import IDraftRepository


class DraftRepository(IDraftRepository):
    """草稿文件系统持久化。"""

    def __init__(self, editor_workflow):
        self._editor = editor_workflow

    def save(
        self,
        original_content: str,
        topic: str,
        source_filepath: str = "",
        meta: str = "",
    ) -> str:
        return self._editor.save_draft(
            original_content=original_content,
            topic=topic,
            source_filepath=source_filepath,
            meta=meta,
        )

    def get(self, draft_id: str) -> Optional[Dict]:
        return self._editor.get_draft(draft_id)

    def list_all(self, status: Optional[str] = None) -> List[Dict]:
        return self._editor.get_all_drafts(status=status)

    def update_edited(
        self, draft_id: str, edited_content: str, edit_note: str
    ) -> bool:
        return self._editor.update_edited(draft_id, edited_content, edit_note)

    def finalize(self, draft_id: str) -> bool:
        return self._editor.finalize(draft_id)

    def get_diff(self, draft_id: str) -> Tuple[str, str]:
        return self._editor.get_diff(draft_id)

    def build_de_ai_prompt(self, content: str) -> str:
        return self._editor.build_de_ai_prompt(content)

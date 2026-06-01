"""Editor domain application DTOs."""

from dataclasses import dataclass


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

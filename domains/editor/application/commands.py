"""Editor domain write-model commands."""

from dataclasses import dataclass


@dataclass
class SaveDraftCommand:
    """Command to save a new draft."""

    original_content: str
    topic: str = ""
    source_filepath: str = ""
    meta: str = ""
    angle: str = ""
    draft_id: str = ""


@dataclass
class UpdateDraftCommand:
    """Command to update an existing draft."""

    draft_id: str
    edited_content: str
    edit_note: str = ""
    finalize: bool = False


@dataclass
class DeAIOptimizeCommand:
    """Command to de-AI-optimize content."""

    content: str

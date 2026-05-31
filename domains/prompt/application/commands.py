"""Prompt domain write-model commands."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SaveSystemTemplateCommand:
    """Command to persist a system prompt template."""

    system_prompt: str


@dataclass
class PreviewPromptsCommand:
    """Command to preview prompt build result."""

    data: Dict[str, object]

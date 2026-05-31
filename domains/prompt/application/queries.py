"""Prompt domain read-model queries."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class GetTemplateContextQuery:
    """Query for prompt template context."""


@dataclass
class GetResourcesContextQuery:
    """Query for resources context."""


@dataclass
class GetModelStatusQuery:
    """Query for LLM model status."""


@dataclass
class BuildPromptsQuery:
    """Query to build system + user prompts."""

    data: Dict[str, object]

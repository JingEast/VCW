"""Editor domain read-model queries."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GetDraftQuery:
    """Query for a single draft."""

    draft_id: str


@dataclass
class ListDraftsQuery:
    """Query for draft list."""

    status: Optional[str] = None


@dataclass
class GetDiffQuery:
    """Query for diff between original and edited."""

    draft_id: str

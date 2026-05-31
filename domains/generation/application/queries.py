"""Generation domain read-model queries."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class GetAsyncStatusQuery:
    """Query for async task status."""

    task_id: str


@dataclass
class GenerateStreamQuery:
    """Query for SSE streaming generation."""

    req_data: Dict[str, object]


@dataclass
class GetAsyncBatchStatusQuery:
    """Query for async batch task status."""

    batch_id: str

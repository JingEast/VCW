"""Generation domain write-model commands."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class GenerateCopyCommand:
    """Command to generate a single copy."""

    req_data: Dict[str, object]


@dataclass
class GenerateBatchCommand:
    """Command to generate a batch of copies."""

    req_data: Dict[str, object]
    angles: List[str]


@dataclass
class SubmitAsyncCommand:
    """Command to submit an async generation task."""

    req_data: Dict[str, object]


@dataclass
class CancelAsyncCommand:
    """Command to cancel an async generation task."""

    task_id: str


@dataclass
class SubmitAsyncBatchCommand:
    """Command to submit an async batch generation task."""

    req_data: Dict[str, object]
    angles: List[str]


@dataclass
class CancelAsyncBatchCommand:
    """Command to cancel an async batch generation task."""

    batch_id: str

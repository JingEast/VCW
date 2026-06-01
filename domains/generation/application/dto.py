"""Generation domain application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class AsyncTaskSubmitDto:
    """异步单任务提交 DTO。"""

    req_data: Dict


@dataclass(frozen=True)
class AsyncBatchSubmitDto:
    """异步批量任务提交 DTO。"""

    req_data: Dict
    angles: List[str]

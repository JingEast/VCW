"""
Editor Domain
=============

精修编辑器领域的核心业务模型。
"""

from .entity import Draft
from .value_object import DraftId, DraftStatus, EditRecord, DeAIPrompt
from .service import DiffEngine, DeAIOptimizer

__all__ = [
    "Draft",
    "DraftId",
    "DraftStatus",
    "EditRecord",
    "DeAIPrompt",
    "DiffEngine",
    "DeAIOptimizer",
]

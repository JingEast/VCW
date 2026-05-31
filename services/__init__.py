"""
VCW Service Layer
=================

项目根级服务层，用于将业务逻辑从 Flask Routes 中抽离到可独立测试的服务类。
"""

from .base import BaseService, PermissionManager, PermissionDenied, TransactionManager
from .generation_service import GenerationService, GenerationError
from .editor_service import (
    EditorService,
    EditorError,
    SaveDraftRequest,
    UpdateDraftRequest,
    DeAIOptimizeRequest,
    DraftResponse,
    DraftListResponse,
    DiffResponse,
    DeAIOptimizeResponse,
)
from .prompt_service import PromptService, PromptError
from .scheduler_service import SchedulerService, SchedulerError
from .history_service import HistoryService, HistoryError

__all__ = [
    "BaseService",
    "PermissionManager",
    "PermissionDenied",
    "TransactionManager",
    "GenerationService",
    "GenerationError",
    "EditorService",
    "EditorError",
    "SaveDraftRequest",
    "UpdateDraftRequest",
    "DeAIOptimizeRequest",
    "DraftResponse",
    "DraftListResponse",
    "DiffResponse",
    "DeAIOptimizeResponse",
    "PromptService",
    "PromptError",
    "SchedulerService",
    "SchedulerError",
    "HistoryService",
    "HistoryError",
]

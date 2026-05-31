"""
Generation Domain
=================

文案生成领域的核心业务模型。
"""

from .entity import Copy, GenerationTask
from .value_object import (
    Audience,
    GenerationParams,
    Prompt,
    QualityIssue,
    QualityReport,
    Topic,
)
from .service import QualityChecker

__all__ = [
    "Copy",
    "GenerationTask",
    "Audience",
    "GenerationParams",
    "Prompt",
    "QualityIssue",
    "QualityReport",
    "Topic",
    "QualityChecker",
]

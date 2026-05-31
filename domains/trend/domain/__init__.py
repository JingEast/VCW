"""
Trend Domain
============

热点发现领域的核心业务模型。
"""

from .entity import Trend
from .value_object import (
    Category,
    HeatLevel,
    TimelinessScore,
    TrendFilter,
    TrendId,
    TrendReport,
)
from .service import TrendClassifier, TrendFilterEngine, TrendScorer

__all__ = [
    "Trend",
    "Category",
    "HeatLevel",
    "TimelinessScore",
    "TrendFilter",
    "TrendId",
    "TrendReport",
    "TrendClassifier",
    "TrendFilterEngine",
    "TrendScorer",
]

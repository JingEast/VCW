"""
Trend Domain — Value Object
===========================

热点发现领域的值对象集合。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TrendId:
    """热点唯一标识（值对象）。"""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("TrendId cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Category:
    """热点分类（值对象）。"""

    value: str

    VALID_CATEGORIES = {
        "DSE",
        "升学",
        "政策",
        "插班",
        "留学",
        "联考",
        "其他",
    }

    def __post_init__(self):
        if not self.value:
            raise ValueError("Category cannot be empty")

    def is_valid(self) -> bool:
        return self.value in self.VALID_CATEGORIES


@dataclass(frozen=True)
class TimelinessScore:
    """
    时效性评分（值对象）。

    范围 0-100，越高表示越新鲜。
    """

    value: float

    def __post_init__(self):
        if not (0 <= self.value <= 100):
            raise ValueError("TimelinessScore must be between 0 and 100")

    def is_hot(self, threshold: float = 60.0) -> bool:
        return self.value >= threshold

    def is_cold(self, threshold: float = 30.0) -> bool:
        return self.value < threshold


@dataclass(frozen=True)
class HeatLevel:
    """
    热度等级（值对象）。

    将原始热度值（0-100）映射为离散等级。
    """

    value: int

    def __post_init__(self):
        if not (0 <= self.value <= 100):
            raise ValueError("HeatLevel must be between 0 and 100")

    @property
    def label(self) -> str:
        if self.value >= 80:
            return "🔥 爆"
        elif self.value >= 60:
            return "🔥 热"
        elif self.value >= 40:
            return "🔥 温"
        elif self.value >= 20:
            return "🧊 凉"
        else:
            return "🧊 冷"


@dataclass(frozen=True)
class TrendFilter:
    """
    热点查询过滤器（值对象）。

    用于分页和筛选查询。
    """

    time_filter: str = "all"  # all, 24h, 7d, 30d
    sort_by: str = "composite"  # composite, time, heat
    category_filter: str = "all"
    limit: int = 25
    offset: int = 0

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("Limit must be >= 1")
        if self.offset < 0:
            raise ValueError("Offset must be >= 0")


@dataclass(frozen=True)
class TrendReport:
    """
    热点统计报告（值对象）。

    用于首页数据看板。
    """

    total_count: int
    category_distribution: dict[str, int]
    freshness_distribution: dict[str, int]  # fresh, stale, expired
    avg_heat: float
    top_trends: List[str]  # trend titles

"""
Trend Domain — Domain Service
=============================

热点发现领域的无状态业务逻辑服务。
"""

from datetime import datetime, timedelta
from typing import List

from .entity import Trend
from .value_object import Category, TimelinessScore, TrendFilter


class TrendScorer:
    """
    热点评分器（领域服务）。

    计算热点的时效性评分和综合得分。
    """

    @staticmethod
    def calc_timeliness_score(trend: Trend) -> TimelinessScore:
        """
        计算时效性评分。

        基于发布时间与当前时间的差值，以及热点的新鲜度。
        范围 0-100。
        """
        if not trend.published_at:
            return TimelinessScore(0.0)

        try:
            published = datetime.fromisoformat(trend.published_at)
        except ValueError:
            return TimelinessScore(0.0)

        now = datetime.now()
        age_hours = (now - published).total_seconds() / 3600

        # 24h 内满分 100，7 天内线性衰减到 70，30 天衰减到 40，90 天衰减到 10
        if age_hours <= 24:
            score = 100.0
        elif age_hours <= 7 * 24:
            score = 100.0 - (age_hours - 24) / (7 * 24 - 24) * 30.0
        elif age_hours <= 30 * 24:
            score = 70.0 - (age_hours - 7 * 24) / (30 * 24 - 7 * 24) * 30.0
        elif age_hours <= 90 * 24:
            score = 40.0 - (age_hours - 30 * 24) / (90 * 24 - 30 * 24) * 30.0
        else:
            score = 10.0 - min((age_hours - 90 * 24) / (365 * 24 - 90 * 24) * 10.0, 10.0)

        return TimelinessScore(max(0.0, score))

    @staticmethod
    def calc_composite_score(trend: Trend) -> float:
        """
        计算综合评分。

        综合 = 时效性 * 0.5 + 热度 * 0.5
        """
        timeliness = TrendScorer.calc_timeliness_score(trend)
        return timeliness.value * 0.5 + trend.heat * 0.5


class TrendClassifier:
    """
    热点分类器（领域服务）。

    根据标题和摘要推断热点分类。
    """

    KEYWORDS = {
        "DSE": ["DSE", "考评局", "文凭试", "放榜", "选科", "公民科"],
        "升学": ["升学", "大学", "录取", "JUPAS", "联招", "改选", "offer"],
        "政策": ["政策", "教育局", "公告", "新规", "调整", "改革"],
        "插班": ["插班", "学位", "派位", "Band1", "直资", "申请"],
        "留学": ["留学", "英国", "澳洲", "海外", "IB", "A-Level"],
        "联考": ["联考", "港澳台", "全国联招", "两校联招"],
    }

    @classmethod
    def classify(cls, title: str, summary: str = "") -> Category:
        """根据标题和摘要推断分类。"""
        text = (title + " " + summary).lower()

        scores: dict[str, int] = {}
        for cat, keywords in cls.KEYWORDS.items():
            scores[cat] = sum(1 for kw in keywords if kw.lower() in text)

        if not scores or max(scores.values()) == 0:
            return Category("其他")

        best = max(scores, key=lambda k: scores[k])
        return Category(best)


class TrendFilterEngine:
    """
    热点过滤引擎（领域服务）。

    对 Trend 列表应用过滤器。
    """

    @staticmethod
    def apply(trends: List[Trend], filter_: TrendFilter) -> List[Trend]:
        """应用过滤器并返回结果。"""
        result = trends

        # 分类过滤
        if filter_.category_filter != "all":
            result = [t for t in result if t.category.value == filter_.category_filter]

        # 时间过滤
        if filter_.time_filter != "all":
            now = datetime.now()
            if filter_.time_filter == "24h":
                cutoff = now - timedelta(hours=24)
            elif filter_.time_filter == "7d":
                cutoff = now - timedelta(days=7)
            elif filter_.time_filter == "30d":
                cutoff = now - timedelta(days=30)
            else:
                cutoff = None

            if cutoff:
                result = [
                    t for t in result
                    if t.published_at and datetime.fromisoformat(t.published_at) >= cutoff
                ]

        # 排序
        if filter_.sort_by == "time":
            result.sort(
                key=lambda t: t.published_at if t.published_at else "",
                reverse=True,
            )
        elif filter_.sort_by == "heat":
            result.sort(key=lambda t: t.heat, reverse=True)
        else:  # composite
            result.sort(
                key=lambda t: TrendScorer.calc_composite_score(t),
                reverse=True,
            )

        # 分页
        paginated = result[filter_.offset: filter_.offset + filter_.limit]
        return paginated

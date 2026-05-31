"""Trend domain repository implementations (Adapter)."""

from typing import Dict, List, Optional, Tuple

from domains.trend.domain.repository import ISchedulerRepository, ITrendRepository


class TrendRepository(ITrendRepository):
    """热点 JSON 数据库持久化。"""

    def __init__(self, trend_db):
        self._db = trend_db

    def import_many(self, trends: List[Dict]) -> Tuple[int, int]:
        return self._db.import_from_scraper(trends)

    def get_all(
        self,
        limit: int = 25,
        offset: int = 0,
        time_filter: str = "all",
        sort_by: str = "composite",
        category_filter: str = "all",
    ) -> Tuple[List[Dict], int]:
        return self._db.get_all(
            limit=limit,
            offset=offset,
            time_filter=time_filter,
            sort_by=sort_by,
            category_filter=category_filter,
        )

    def get_fresh(self, limit: int = 5) -> List[Dict]:
        return self._db.get_fresh_hotspots(limit=limit)

    def get_by_id(self, trend_id: str) -> Optional[Dict]:
        return self._db.get_by_id(trend_id)

    def generate_report(self) -> str:
        return self._db.generate_report()

    def delete(self, trend_id: str) -> None:
        self._db.delete(trend_id)

    def delete_expired(self) -> int:
        return self._db.delete_expired()

    def archive_stale(self) -> int:
        return self._db.delete_stale()

    def add_manual(
        self,
        title: str,
        summary: str = "",
        url: str = "",
        published_at: str = "",
    ) -> str:
        return self._db.add_manual(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )

    def select(self, trend_id: str) -> None:
        self._db.select(trend_id)

    def calc_timeliness(self, trend: Dict) -> int:
        return self._db._calc_timeliness_score(trend)


class SchedulerRepository(ISchedulerRepository):
    """调度器适配器。"""

    def __init__(self, scheduler):
        self._scheduler = scheduler

    def get_status(self) -> Dict:
        return self._scheduler.get_status()

    def enable(self, interval_minutes: int) -> None:
        self._scheduler.enable(interval_minutes=interval_minutes)

    def disable(self) -> None:
        self._scheduler.disable()

    def trigger_now(self) -> Dict:
        return self._scheduler.trigger_now()

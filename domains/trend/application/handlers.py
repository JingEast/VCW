"""Trend domain application handlers."""

from typing import Dict, List, Optional, Tuple

from .commands import (
    AddManualTrendCommand,
    ArchiveStaleCommand,
    DeleteExpiredCommand,
    DeleteTrendCommand,
    DisableSchedulerCommand,
    EnableSchedulerCommand,
    FetchTrendsCommand,
    SelectTrendCommand,
    TriggerSchedulerCommand,
)
from .queries import (
    GenerateReportQuery,
    GetFreshHotspotsQuery,
    GetSchedulerStatusQuery,
    GetTrendDetailQuery,
    ListTrendsQuery,
)


class TrendHandler:
    """Orchestrates trend use cases."""

    def __init__(self, scheduler_service):
        self._svc = scheduler_service

    def handle_fetch_trends(self, command: FetchTrendsCommand) -> Tuple[int, int]:
        return self._svc.fetch_trends_manually(
            force=command.force, include_expired=command.include_expired
        )

    def handle_select_trend(self, command: SelectTrendCommand) -> Dict:
        return self._svc.select_trend(command.trend_id)

    def handle_delete_trend(self, command: DeleteTrendCommand) -> None:
        self._svc.delete_trend(command.trend_id)

    def handle_delete_expired(self, command: DeleteExpiredCommand) -> int:
        return self._svc.delete_expired()

    def handle_archive_stale(self, command: ArchiveStaleCommand) -> int:
        return self._svc.archive_stale()

    def handle_add_manual_trend(self, command: AddManualTrendCommand) -> str:
        return self._svc.add_manual_trend(
            title=command.title,
            summary=command.summary,
            url=command.url,
            published_at=command.published_at,
        )

    def handle_enable_scheduler(self, command: EnableSchedulerCommand) -> None:
        self._svc.enable(command.interval_minutes)

    def handle_disable_scheduler(self, command: DisableSchedulerCommand) -> None:
        self._svc.disable()

    def handle_trigger_scheduler(self, command: TriggerSchedulerCommand) -> Dict:
        return self._svc.trigger_now()

    def handle_list_trends(
        self, query: ListTrendsQuery
    ) -> Tuple[List[Dict], int]:
        return self._svc.list_trends(
            page=query.page,
            per_page=query.per_page,
            time_filter=query.time_filter,
            sort_by=query.sort_by,
            category_filter=query.category_filter,
        )

    def handle_get_fresh_hotspots(
        self, query: GetFreshHotspotsQuery
    ) -> List[Dict]:
        return self._svc.get_fresh_hotspots(query.limit)

    def handle_get_trend_detail(
        self, query: GetTrendDetailQuery
    ) -> Optional[Dict]:
        return self._svc.get_trend_detail(query.trend_id)

    def handle_get_scheduler_status(self, query: GetSchedulerStatusQuery) -> Dict:
        return self._svc.get_status()

    def handle_generate_report(self, query: GenerateReportQuery) -> str:
        return self._svc.generate_report()

    def handle_calc_timeliness_score(self, trend: Dict) -> int:
        return self._svc.calc_timeliness_score(trend)

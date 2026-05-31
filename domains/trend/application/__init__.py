"""Trend domain application layer."""

from .commands import (
    FetchTrendsCommand,
    SelectTrendCommand,
    DeleteTrendCommand,
    DeleteExpiredCommand,
    ArchiveStaleCommand,
    AddManualTrendCommand,
    EnableSchedulerCommand,
    DisableSchedulerCommand,
    TriggerSchedulerCommand,
)
from .queries import (
    ListTrendsQuery,
    GetFreshHotspotsQuery,
    GetTrendDetailQuery,
    GetSchedulerStatusQuery,
    GenerateReportQuery,
)
from .handlers import TrendHandler

__all__ = [
    "FetchTrendsCommand",
    "SelectTrendCommand",
    "DeleteTrendCommand",
    "DeleteExpiredCommand",
    "ArchiveStaleCommand",
    "AddManualTrendCommand",
    "EnableSchedulerCommand",
    "DisableSchedulerCommand",
    "TriggerSchedulerCommand",
    "ListTrendsQuery",
    "GetFreshHotspotsQuery",
    "GetTrendDetailQuery",
    "GetSchedulerStatusQuery",
    "GenerateReportQuery",
    "TrendHandler",
]

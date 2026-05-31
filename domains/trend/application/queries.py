"""Trend domain read-model queries."""

from dataclasses import dataclass


@dataclass
class ListTrendsQuery:
    """Query for paginated trend list."""

    page: int = 1
    per_page: int = 25
    time_filter: str = "all"
    sort_by: str = "composite"
    category_filter: str = "all"


@dataclass
class GetFreshHotspotsQuery:
    """Query for fresh hotspot trends."""

    limit: int = 5


@dataclass
class GetTrendDetailQuery:
    """Query for a single trend detail."""

    trend_id: str


@dataclass
class GetSchedulerStatusQuery:
    """Query for scheduler status."""


@dataclass
class GenerateReportQuery:
    """Query for trend report generation."""

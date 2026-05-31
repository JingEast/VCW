"""Trend domain write-model commands."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchTrendsCommand:
    """Command to manually fetch fresh trends."""

    force: bool = True
    include_expired: bool = False


@dataclass
class SelectTrendCommand:
    """Command to select a trend for generation."""

    trend_id: str


@dataclass
class DeleteTrendCommand:
    """Command to delete a trend."""

    trend_id: str


@dataclass
class DeleteExpiredCommand:
    """Command to delete expired trends."""


@dataclass
class ArchiveStaleCommand:
    """Command to archive stale trends."""


@dataclass
class AddManualTrendCommand:
    """Command to add a manually created trend."""

    title: str
    summary: str = ""
    url: str = ""
    published_at: Optional[str] = None


@dataclass
class EnableSchedulerCommand:
    """Command to enable the background scheduler."""

    interval_minutes: int = 60


@dataclass
class DisableSchedulerCommand:
    """Command to disable the background scheduler."""


@dataclass
class TriggerSchedulerCommand:
    """Command to trigger the scheduler immediately."""

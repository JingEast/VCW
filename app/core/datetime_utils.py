"""UTC 时间工具。

消除 datetime.utcnow() 弃用警告（Python 3.12+），
同时保持返回 naive datetime 以兼容现有数据库列。
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回当前 UTC 时间的 naive datetime 对象。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

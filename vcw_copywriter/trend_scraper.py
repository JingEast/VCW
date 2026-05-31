"""
热点爬虫模块 v2.0 — Provider + Pipeline 架构入口

原 2000+ 行 God Object 已拆分为 scraper/ 包：
  - Providers: RSS / HTML / Playwright / GoogleNews / BaiduHot
  - Pipelines: Filter / Dedupe / Normalize
  - Utils: TimeParser / RelevanceCalculator / HttpClient

此文件作为薄入口，重新导出公共 API 与配置常量，保持向后兼容。
"""
from .scraper import (
    TrendScraper,
    fetch_trends,
)
from .scraper.config import (
    SEARCH_KEYWORDS,
    NEWS_SITES,
    RSS_SOURCES,
    WECHAT_ACCOUNTS,
    EDU_SITES,
    STALE_DAYS,
    EXPIRED_DAYS,
    TIME_WEIGHT_FACTOR,
)

__all__ = [
    "TrendScraper",
    "fetch_trends",
    "SEARCH_KEYWORDS",
    "NEWS_SITES",
    "RSS_SOURCES",
    "WECHAT_ACCOUNTS",
    "EDU_SITES",
    "STALE_DAYS",
    "EXPIRED_DAYS",
    "TIME_WEIGHT_FACTOR",
]

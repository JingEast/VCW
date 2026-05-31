"""
定时调度服务层
==============

统管热点爬取调度器的生命周期（启用/禁用/手动触发）
以及热点数据库的查询、清理、归档和手动录入。
"""

import logging
from typing import Dict, List, Optional, Tuple

from services.base.base_service import BaseService
from services.base.permission_manager import PermissionDenied
from domains.trend.domain.repository import ISchedulerRepository, ITrendRepository

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """调度器业务异常"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class SchedulerService(BaseService):
    """
    定时调度与热点管理服务。

    作为 TrendRepository + SchedulerRepository 的门面（Facade），
    向路由层提供高阶的调度与热点管理接口。
    """

    def __init__(
        self,
        config,
        scheduler_repo: ISchedulerRepository,
        trend_repo: ITrendRepository,
        transaction_manager=None,
        permission_manager=None,
    ) -> None:
        super().__init__(config, transaction_manager, permission_manager)
        self.scheduler_repo = scheduler_repo
        self.trend_repo = trend_repo

    def _on_permission_denied(self, exc: PermissionDenied) -> None:
        raise SchedulerError(exc.message, code=exc.code)

    # ------------------------------------------------------------------
    # 调度器生命周期
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        logger.info("获取调度器状态")
        return self.scheduler_repo.get_status()

    def enable(self, interval_minutes: int = 60) -> None:
        logger.info("启用定时爬取，间隔 %d 分钟", interval_minutes)
        self.scheduler_repo.enable(interval_minutes=interval_minutes)

    def disable(self) -> None:
        logger.info("禁用定时爬取")
        self.scheduler_repo.disable()

    def trigger_now(self) -> Dict:
        logger.info("手动触发爬取")
        return self.scheduler_repo.trigger_now()

    # ------------------------------------------------------------------
    # 热点爬取与导入
    # ------------------------------------------------------------------

    def fetch_trends_manually(
        self,
        force: bool = True,
        include_expired: bool = False,
    ) -> Tuple[int, int]:
        logger.info("手动执行热点爬取")
        from vcw_copywriter.trend_scraper import TrendScraper

        scraper = TrendScraper()
        trends = scraper.fetch_all(force=force, include_expired=include_expired)
        added, skipped = self.trend_repo.import_many(trends)
        logger.info("爬取完成：新增 %d 条，跳过 %d 条", added, skipped)
        return added, skipped

    # ------------------------------------------------------------------
    # 热点查询
    # ------------------------------------------------------------------

    def list_trends(
        self,
        page: int = 1,
        per_page: int = 25,
        time_filter: str = "all",
        sort_by: str = "composite",
        category_filter: str = "all",
    ) -> Tuple[List[Dict], int]:
        logger.debug(
            "查询热点列表: page=%d, per_page=%d, time_filter=%s, sort_by=%s, category=%s",
            page, per_page, time_filter, sort_by, category_filter,
        )
        offset = (page - 1) * per_page
        return self.trend_repo.get_all(
            limit=per_page,
            offset=offset,
            time_filter=time_filter,
            sort_by=sort_by,
            category_filter=category_filter,
        )

    def get_fresh_hotspots(self, limit: int = 5) -> List[Dict]:
        logger.debug("获取最新热点，上限 %d", limit)
        return self.trend_repo.get_fresh(limit=limit)

    def get_trend_detail(self, trend_id: str) -> Optional[Dict]:
        logger.debug("获取热点详情: %s", trend_id)
        return self.trend_repo.get_by_id(trend_id)

    def generate_report(self) -> str:
        logger.debug("生成热点报告")
        return self.trend_repo.generate_report()

    # ------------------------------------------------------------------
    # 热点维护
    # ------------------------------------------------------------------

    def delete_trend(self, trend_id: str) -> None:
        logger.info("删除热点: %s", trend_id)
        self.trend_repo.delete(trend_id)

    def delete_expired(self) -> int:
        logger.info("清理过期热点")
        deleted = self.trend_repo.delete_expired()
        logger.info("清理完成：%d 条", deleted)
        return deleted

    def archive_stale(self) -> int:
        logger.info("归档陈旧热点")
        archived = self.trend_repo.archive_stale()
        logger.info("归档完成：%d 条", archived)
        return archived

    def add_manual_trend(
        self,
        title: str,
        summary: str = "",
        url: str = "",
        published_at: str = "",
    ) -> str:
        if not title:
            raise SchedulerError("标题不能为空", code="MISSING_TITLE")
        logger.info("手动录入热点: %s", title)
        trend_id = self.trend_repo.add_manual(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )
        logger.info("手动录入成功: %s", trend_id)
        return trend_id

    def select_trend(self, trend_id: str) -> Dict:
        logger.info("选用热点: %s", trend_id)
        trend = self.trend_repo.get_by_id(trend_id)
        if not trend:
            raise SchedulerError("热点不存在", code="TREND_NOT_FOUND")

        self.trend_repo.select(trend_id)

        from vcw_copywriter.auto_prompt import auto_fill_from_trend

        auto_params = auto_fill_from_trend(trend)
        logger.info("热点选用完成，已生成自动参数")
        return auto_params

    def calc_timeliness_score(self, trend: Dict) -> int:
        return self.trend_repo.calc_timeliness(trend)

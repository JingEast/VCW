"""Trend domain repository interfaces (Port)."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


class ITrendRepository(ABC):
    """热点数据持久化接口。"""

    @abstractmethod
    def import_many(self, trends: List[Dict]) -> Tuple[int, int]:
        """批量导入热点，返回 (added, skipped)。"""

    @abstractmethod
    def get_all(
        self,
        limit: int = 25,
        offset: int = 0,
        time_filter: str = "all",
        sort_by: str = "composite",
        category_filter: str = "all",
    ) -> Tuple[List[Dict], int]:
        """分页查询热点列表。"""

    @abstractmethod
    def get_fresh(self, limit: int = 5) -> List[Dict]:
        """获取最新热点。"""

    @abstractmethod
    def get_by_id(self, trend_id: str) -> Optional[Dict]:
        """根据 ID 获取热点。"""

    @abstractmethod
    def generate_report(self) -> str:
        """生成热点统计报告。"""

    @abstractmethod
    def delete(self, trend_id: str) -> None:
        """删除热点。"""

    @abstractmethod
    def delete_expired(self) -> int:
        """清理过期热点，返回清理数量。"""

    @abstractmethod
    def archive_stale(self) -> int:
        """归档陈旧热点，返回归档数量。"""

    @abstractmethod
    def add_manual(
        self,
        title: str,
        summary: str = "",
        url: str = "",
        published_at: str = "",
    ) -> str:
        """手动录入热点，返回 trend_id。"""

    @abstractmethod
    def select(self, trend_id: str) -> None:
        """标记热点为已选用。"""

    @abstractmethod
    def calc_timeliness(self, trend: Dict) -> int:
        """计算时效性评分。"""


class ISchedulerRepository(ABC):
    """调度器状态与操作接口。"""

    @abstractmethod
    def get_status(self) -> Dict:
        """获取调度器状态。"""

    @abstractmethod
    def enable(self, interval_minutes: int) -> None:
        """启用定时爬取。"""

    @abstractmethod
    def disable(self) -> None:
        """禁用定时爬取。"""

    @abstractmethod
    def trigger_now(self) -> Dict:
        """立即触发爬取。"""

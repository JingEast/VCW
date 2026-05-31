"""Generation domain repository interfaces (Port)."""

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional, Tuple


class ICopyRepository(ABC):
    """文案持久化接口。"""

    @abstractmethod
    def save(self, content: str, topic: str, meta: object, output_dir: str) -> str:
        """保存生成的文案，返回文件路径。"""

    @abstractmethod
    def find_recent(self, limit: int, output_dir: str) -> List[Dict]:
        """获取最近的生成文件列表。"""

    @abstractmethod
    def get_stats(self, output_dir: str) -> Dict:
        """获取生成统计信息。"""


class ITaskRepository(ABC):
    """异步任务队列接口。"""

    @abstractmethod
    def submit(self, task_type: str, worker_fn) -> str:
        """提交异步任务，返回 task_id。"""

    @abstractmethod
    def get_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态。"""

    @abstractmethod
    def cancel(self, task_id: str) -> bool:
        """取消任务。"""


class IMemoryRepository(ABC):
    """记忆库接口。"""

    @abstractmethod
    def format_memories(self, topic: str) -> str:
        """获取格式化的记忆文本。"""

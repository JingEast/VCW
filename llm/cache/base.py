"""Cache 后端抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from llm.adapter.base import LLMResponse


@dataclass(frozen=True)
class CacheEntry:
    """缓存条目。"""

    response: LLMResponse
    ttl_seconds: int


class BaseCacheBackend(ABC):
    """缓存后端抽象基类。

    缓存 key 由 Gateway 通过 _make_cache_key 生成（基于 prompt hash），
    后端只负责 get/set/delete。
    """

    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """根据 key 获取缓存条目。"""
        ...

    @abstractmethod
    def set(self, key: str, entry: CacheEntry) -> None:
        """写入缓存条目。"""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存条目，返回是否成功。"""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存。"""
        ...

    def make_key(self, messages: list[dict[str, str]], provider: str, **kwargs: Any) -> str:
        """基于消息内容生成缓存 key。

        默认实现使用 SHA256 哈希，子类可覆盖。
        """
        import hashlib
        import json

        data: dict[str, Any] = {
            "messages": messages,
            "provider": provider,
        }
        data.update(kwargs)
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

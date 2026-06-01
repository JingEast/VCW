"""内存缓存后端（开发/测试使用）。"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional

from .base import BaseCacheBackend, CacheEntry


class MemoryCacheBackend(BaseCacheBackend):
    """基于 dict 的内存缓存，使用显式锁保证线程安全。

    生产环境建议替换为 RedisCacheBackend。
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._store: Dict[str, tuple[CacheEntry, float]] = {}
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            entry, expiry = item
            if time.time() > expiry:
                self._store.pop(key, None)
                return None
            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                # 简单 LRU：删除最早的一条
                oldest = next(iter(self._store))
                self._store.pop(oldest, None)
            expiry = time.time() + entry.ttl_seconds
            self._store[key] = (entry, expiry)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

"""LLM 响应缓存。

支持：
  - 内存缓存（开发/测试）
  - Redis 缓存（生产）
  - 基于 prompt hash 的 key 生成
"""

from .base import BaseCacheBackend, CacheEntry

__all__ = [
    "BaseCacheBackend",
    "CacheEntry",
]

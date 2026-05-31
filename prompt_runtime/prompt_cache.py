"""Prompt 缓存 —— 基于内容的响应复用。

职责：
  1. 对 (system_prompt, user_prompt, model, temperature) 做哈希缓存。
  2. 支持 TTL 过期和显式失效。
  3. 支持内存缓存与 Redis 缓存双后端。
  4. 减少重复 LLM 调用成本。
"""

from __future__ import annotations

import hashlib
import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CacheEntry:
    """缓存条目。"""

    key: str
    result: object
    created_at: datetime
    ttl_seconds: int = 3600

    def is_expired(self) -> bool:
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds


class HashKeyStrategy:
    """基于 Prompt 内容生成确定性哈希键。"""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成 SHA256 哈希键。"""
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra": extra or {},
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class IPromptCache(ABC):
    """Prompt 缓存接口。"""

    @abstractmethod
    def get(self, key: str) -> Optional[object]:
        """获取缓存值；过期时返回 None。"""

    @abstractmethod
    def set(self, key: str, result: object, ttl_seconds: int = 3600) -> None:
        """写入缓存。"""

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """使单个缓存失效。"""

    @abstractmethod
    def clear(self) -> None:
        """清空全部缓存。"""


class PromptCache(IPromptCache):
    """内存实现的 Prompt 缓存（dict + TTL）。"""

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[object]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            self._store.pop(key, None)
            return None
        return entry.result

    def set(self, key: str, result: object, ttl_seconds: int = 3600) -> None:
        self._store[key] = CacheEntry(
            key=key,
            result=result,
            created_at=datetime.now(),
            ttl_seconds=ttl_seconds,
        )

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


class RedisPromptCache(IPromptCache):
    """Redis 实现的 Prompt 缓存。

    使用 pickle 序列化结果对象，支持任意类型。
    当 Redis 不可用时，可优雅降级为内存缓存（如提供 fallback_store）。
    """

    def __init__(
        self,
        redis_client=None,
        key_prefix: str = "prompt_cache:",
        fallback_store: Optional[IPromptCache] = None,
    ) -> None:
        self._redis = redis_client
        self._prefix = key_prefix
        self._fallback = fallback_store

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Optional[object]:
        if self._redis is None:
            return self._fallback.get(key) if self._fallback else None
        try:
            raw = self._redis.get(self._make_key(key))
            if raw is None:
                return None
            return pickle.loads(raw)
        except Exception:
            return self._fallback.get(key) if self._fallback else None

    def set(self, key: str, result: object, ttl_seconds: int = 3600) -> None:
        if self._redis is None:
            if self._fallback:
                self._fallback.set(key, result, ttl_seconds)
            return
        try:
            self._redis.setex(
                self._make_key(key),
                ttl_seconds,
                pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL),
            )
        except Exception:
            if self._fallback:
                self._fallback.set(key, result, ttl_seconds)

    def invalidate(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(self._make_key(key))
            except Exception:
                pass
        if self._fallback:
            self._fallback.invalidate(key)

    def clear(self) -> None:
        if self._redis is not None:
            try:
                for k in self._redis.scan_iter(match=f"{self._prefix}*"):
                    self._redis.delete(k)
            except Exception:
                pass
        if self._fallback:
            self._fallback.clear()

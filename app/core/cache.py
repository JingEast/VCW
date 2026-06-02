"""轻量级线程安全内存缓存（TTL）。

提供 @cached 装饰器，用于缓存函数返回值。
零外部依赖，适合 Repository / Service 层热点数据缓存。
"""

from __future__ import annotations

import threading
import time
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable)


class LocalTTLCache:
    """线程安全的内存 TTL 缓存。"""

    def __init__(self, ttl: float, maxsize: int = 128) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: dict[Any, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any:
        with self._lock:
            if key not in self._store:
                raise KeyError(key)
            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                raise KeyError(key)
            return value

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize:
                self._evict()
            self._store[key] = (value, time.time() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp < now]
        for k in expired:
            del self._store[k]
        if len(self._store) >= self._maxsize:
            oldest = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest]


def _make_key(func: Callable, args: tuple, kwargs: dict) -> Any:
    def _freeze(obj: Any) -> Any:
        if isinstance(obj, list):
            return tuple(_freeze(x) for x in obj)
        if isinstance(obj, dict):
            return tuple(sorted((k, _freeze(v)) for k, v in obj.items()))
        return obj

    try:
        frozen_args = tuple(_freeze(a) for a in args)
        frozen_kwargs = tuple(sorted((k, _freeze(v)) for k, v in kwargs.items()))
        return (func.__qualname__, frozen_args, frozen_kwargs)
    except TypeError:
        return (func.__qualname__, str(args), str(tuple(sorted(kwargs.items()))))


def cached(ttl_seconds: float = 60, maxsize: int = 128) -> Callable[[F], F]:
    """装饰器：缓存函数返回值 ttl_seconds 秒。

    被装饰的函数会获得两个额外属性：
      - ``wrapper.cache`` -> LocalTTLCache 实例
      - ``wrapper.cache_clear()`` -> 清空该函数缓存

    Args:
        ttl_seconds: 缓存有效期（秒）。
        maxsize: 缓存条目上限，超限后淘汰最早过期的条目。
    """
    cache = LocalTTLCache(ttl=ttl_seconds, maxsize=maxsize)

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_key(func, args, kwargs)
            try:
                return cache.get(key)
            except KeyError:
                result = func(*args, **kwargs)
                cache.set(key, result)
                return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator

#!/usr/bin/env python3
"""
容器启动等待脚本。

在启动主应用前，等待依赖服务（Redis、PostgreSQL）就绪。
用法：
    python scripts/wait-for-services.py [command...]

环境变量：
    WAIT_REDIS_URL      Redis 连接地址（默认 redis://localhost:6379/0）
    WAIT_DATABASE_URL   数据库连接地址（默认空，不等待）
    WAIT_TIMEOUT        最长等待秒数（默认 30）
    WAIT_INTERVAL       重试间隔秒数（默认 2）
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.parse
from typing import Callable, Optional


# ------------------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------------------
_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "30"))
_INTERVAL = int(os.getenv("WAIT_INTERVAL", "2"))


# ------------------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------------------
def _log(msg: str) -> None:
    print(f"[wait-for-services] {msg}", flush=True)


def _wait_redis(url: str) -> bool:
    """等待 Redis 就绪。"""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    start = time.time()
    while time.time() - start < _TIMEOUT:
        try:
            with socket.create_connection((host, port), timeout=2):
                _log(f"Redis at {host}:{port} is ready")
                return True
        except OSError:
            pass
        time.sleep(_INTERVAL)

    _log(f"Redis at {host}:{port} not ready within {_TIMEOUT}s")
    return False


def _wait_postgres(url: str) -> bool:
    """等待 PostgreSQL 就绪（通过 psycopg2 连接测试）。"""
    start = time.time()
    while time.time() - start < _TIMEOUT:
        try:
            import psycopg2
            conn = psycopg2.connect(url, connect_timeout=2)
            conn.close()
            _log("PostgreSQL is ready")
            return True
        except ImportError:
            _log("psycopg2 not installed, skipping PostgreSQL wait")
            return True
        except Exception:
            pass
        time.sleep(_INTERVAL)

    _log(f"PostgreSQL not ready within {_TIMEOUT}s")
    return False


def _wait_sqlite(_url: str) -> bool:
    """SQLite 无需等待。"""
    return True


def _resolve_waiter(url: str) -> Optional[Callable]:
    """根据 URL 前缀返回对应的等待函数。"""
    if url.startswith("redis://") or url.startswith("rediss://"):
        return _wait_redis
    if url.startswith("postgresql://") or url.startswith("postgresql+"):
        return _wait_postgres
    if url.startswith("sqlite://"):
        return _wait_sqlite
    return None


def main() -> int:
    redis_url = os.getenv("WAIT_REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    db_url = os.getenv("WAIT_DATABASE_URL", os.getenv("DATABASE_URL", ""))

    # 等待 Redis（Celery Broker）
    if redis_url:
        waiter = _resolve_waiter(redis_url)
        if waiter and not waiter(redis_url):
            return 1

    # 等待数据库
    if db_url:
        waiter = _resolve_waiter(db_url)
        if waiter and not waiter(db_url):
            return 1

    # 执行后续命令
    if len(sys.argv) > 1:
        _log(f"Starting: {' '.join(sys.argv[1:])}")
        return subprocess.call(sys.argv[1:])

    _log("No command provided; services are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

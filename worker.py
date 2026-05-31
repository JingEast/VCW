"""VCW Celery Worker 启动入口。

使用方式：
    # 开发环境
    python worker.py -l info

    # 生产环境（推荐）
    celery -A celery_app worker -l info -c 4 -Q celery,vcw

环境变量：
    CELERY_BROKER_URL          Redis 连接地址
    CELERY_RESULT_BACKEND      PostgreSQL 连接地址
"""

from __future__ import annotations

import argparse
import sys

from celery_app import app


def main() -> int:
    parser = argparse.ArgumentParser(description="VCW Celery Worker")
    parser.add_argument(
        "-l", "--loglevel",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="日志级别",
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=2,
        help="并发 worker 数",
    )
    parser.add_argument(
        "-Q", "--queues",
        default="celery",
        help="监听的队列，逗号分隔",
    )
    args = parser.parse_args()

    argv = [
        "worker",
        "--loglevel=" + args.loglevel,
        "--concurrency=" + str(args.concurrency),
        "-Q", args.queues,
    ]

    # 将参数传给 Celery
    sys.argv = [sys.argv[0]] + argv
    app.worker_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
日志配置模块

提供统一的日志格式、文件轮转和控制台输出。
禁止直接使用 print，所有输出均通过 logging 模块。
"""

import logging
import logging.handlers
import os
import uuid
from typing import Optional

from flask import Flask, has_request_context


DEFAULT_FORMAT = (
    "[%(asctime)s] %(levelname)-7s trace_id=%(trace_id)s %(name)-20s %(message)s "
    "[%(pathname)s:%(lineno)d]"
)
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


class TraceIdFilter(logging.Filter):
    """
    为每条日志记录注入 trace_id。
    在 Flask 请求上下文中从 g.trace_id 获取；无请求上下文时显示 '-'。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            from flask import g
            record.trace_id = getattr(g, "trace_id", "-")
        else:
            record.trace_id = "-"
        return True


def setup_logging(
    app: Flask,
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    配置 Flask 应用日志。

    Args:
        app: Flask 应用实例
        log_dir: 日志目录，默认项目根目录下的 logs/
        max_bytes: 单个日志文件大小上限（字节）
        backup_count: 保留的轮转备份数量
    """
    if log_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATEFMT)
    trace_filter = TraceIdFilter()

    # 清除根 logger 现有 handlers（避免重复注册）
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    # 文件轮转 Handler
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "vcw.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(trace_filter)

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(trace_filter)

    root.setLevel(log_level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # 同步 Flask app.logger（禁用传播避免重复输出）
    app.logger.handlers = []
    app.logger.propagate = False
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # 在每个请求开始时自动初始化 trace_id，供日志和全局错误处理器复用
    @app.before_request
    def _init_trace_id() -> None:
        from flask import g
        if not hasattr(g, "trace_id"):
            g.trace_id = uuid.uuid4().hex[:12]

    app.logger.info(
        "Logging configured. level=%s dir=%s",
        logging.getLevelName(log_level),
        log_dir,
    )

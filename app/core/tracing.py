"""分布式追踪工具函数。

提供轻量级的 trace_id 获取与 outbound header 注入能力。
不依赖 OpenTelemetry SDK，保持零外部依赖。
"""

from __future__ import annotations

import uuid
from typing import Optional


X_TRACE_ID_HEADER = "X-Trace-Id"


def get_current_trace_id() -> str:
    """获取当前请求上下文的 trace_id。

    优先从 Flask ``g.trace_id`` 获取；不在 Flask 上下文中时生成新的。
    """
    try:
        from flask import g, has_request_context

        if has_request_context():
            return getattr(g, "trace_id", _generate_trace_id())
    except Exception:
        pass
    return _generate_trace_id()


def _generate_trace_id() -> str:
    """生成 12 字符十六进制 trace_id。"""
    return uuid.uuid4().hex[:12]


def make_trace_headers(existing: Optional[dict[str, str]] = None) -> dict[str, str]:
    """创建包含 X-Trace-Id 的请求头字典。

    Args:
        existing: 已有的请求头，会被合并（X-Trace-Id 会覆盖同名键）。
    """
    headers = dict(existing) if existing else {}
    headers[X_TRACE_ID_HEADER] = get_current_trace_id()
    return headers


def make_server_timing_header(duration_ms: float, desc: str = "total") -> str:
    """生成符合 W3C Server-Timing 规范的 header 值。

    格式: ``desc;dur=<milliseconds>``

    Args:
        duration_ms: 耗时（毫秒）。
        desc: 计时项描述（默认 ``total``）。
    """
    return f"{desc};dur={duration_ms:.2f}"

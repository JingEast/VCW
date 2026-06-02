"""Flask-Limiter 共享实例（避免循环导入）。

使用方式：
    from app.core.limiter import limiter
    @limiter.limit("10 per minute")
    def my_view():
        ...
"""

from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
)

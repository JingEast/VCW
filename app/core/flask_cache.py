"""Flask-Caching 实例（避免循环导入）。

使用方式：
    from app.core.flask_cache import cache
    @cache.cached(timeout=300)
    def my_view():
        ...
"""

from __future__ import annotations

from flask_caching import Cache

cache = Cache()

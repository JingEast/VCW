"""Performance tests fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _push_app_context(app):
    """让每个测试函数自动运行在 Flask app 上下文中。"""
    with app.app_context():
        yield


@pytest.fixture(autouse=True)
def _clear_profiler(app):
    """每个测试结束后清空 profiler 记录，避免测试间污染。"""
    yield
    app.profiler.clear()

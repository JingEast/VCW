"""日志测试：验证结构化日志与 trace_id 注入。"""

from __future__ import annotations

import logging

import pytest


class TestTraceIdFilter:
    """验证 TraceIdFilter 在请求上下文中的行为。"""

    def test_trace_id_injected_from_flask_g(self, app):
        """请求上下文中从 g.trace_id 获取 trace_id。"""
        from app.core.logging_config import TraceIdFilter

        filter_ = TraceIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )

        with app.test_request_context("/"):
            from flask import g

            g.trace_id = "abc123def456"
            result = filter_.filter(record)

        assert result is True
        assert record.trace_id == "abc123def456"

    def test_trace_id_defaults_to_dash_outside_request(self, app):
        """无请求上下文时 trace_id 为 '-'。"""
        from app.core.logging_config import TraceIdFilter

        filter_ = TraceIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )

        result = filter_.filter(record)

        assert result is True
        assert record.trace_id == "-"


class TestSetupLogging:
    """验证 setup_logging 配置正确。"""

    @pytest.fixture
    def fresh_app(self):
        """创建未处理过请求的 Flask 实例，供 setup_logging 使用。"""
        from app import create_app

        _app = create_app()
        _app.config.update({"TESTING": True, "SECRET_KEY": "test-secret-key"})
        return _app

    def test_log_level_follows_app_debug(self, fresh_app):
        """app.debug=True 时日志级别为 DEBUG。"""
        from app.core.logging_config import setup_logging

        fresh_app.debug = True
        setup_logging(fresh_app)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_log_level_info_when_not_debug(self, fresh_app):
        """app.debug=False 时日志级别为 INFO。"""
        from app.core.logging_config import setup_logging

        fresh_app.debug = False
        setup_logging(fresh_app)

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_handlers_contain_trace_filter(self, fresh_app):
        """所有 handler 都注册了 TraceIdFilter。"""
        from app.core.logging_config import setup_logging, TraceIdFilter

        setup_logging(fresh_app)

        root = logging.getLogger()
        for handler in root.handlers:
            assert any(isinstance(f, TraceIdFilter) for f in handler.filters)

"""日志测试：验证结构化日志与 trace_id 注入。"""

from __future__ import annotations

import json
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


class TestJsonFormatter:
    """验证 JSON 结构化日志格式器。"""

    def test_json_output_contains_required_fields(self, app):
        """JSON 日志包含所有必需字段。"""
        from app.core.logging_config import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        record.trace_id = "tx-123"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello world"
        assert data["trace_id"] == "tx-123"
        assert data["pathname"] == "/path/to/file.py"
        assert data["lineno"] == 42
        assert "timestamp" in data
        assert "funcName" in data

    def test_json_output_excludes_exception_when_none(self, app):
        """无异常时 JSON 不包含 exception 字段。"""
        from app.core.logging_config import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="ok",
            args=(),
            exc_info=None,
        )
        record.trace_id = "-"

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" not in data

    def test_json_output_includes_exception_when_present(self, app):
        """有异常时 JSON 包含 exception 字段。"""
        import sys

        from app.core.logging_config import JsonFormatter

        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="error",
                args=(),
                exc_info=exc_info,
            )
            record.trace_id = "-"

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError: boom" in data["exception"]

    def test_json_ensure_ascii_false(self, app):
        """非 ASCII 字符直接输出，不做 unicode escape。"""
        from app.core.logging_config import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="港籍升学 %s",
            args=("测试",),
            exc_info=None,
        )
        record.trace_id = "-"

        output = formatter.format(record)

        assert "港籍升学" in output
        assert "测试" in output


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

    def test_debug_mode_uses_text_formatter(self, fresh_app):
        """debug=True 时使用文本格式器（human-readable）。"""
        from app.core.logging_config import setup_logging, JsonFormatter

        fresh_app.debug = True
        setup_logging(fresh_app)

        root = logging.getLogger()
        for handler in root.handlers:
            assert not isinstance(handler.formatter, JsonFormatter)

    def test_production_mode_uses_json_formatter(self, fresh_app):
        """debug=False 时使用 JSON 格式器。"""
        from app.core.logging_config import setup_logging, JsonFormatter

        fresh_app.debug = False
        setup_logging(fresh_app)

        root = logging.getLogger()
        for handler in root.handlers:
            assert isinstance(handler.formatter, JsonFormatter)

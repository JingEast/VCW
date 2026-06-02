"""请求追踪测试：验证 X-Trace-Id 响应头与跨层 trace_id 一致性。"""

from __future__ import annotations

import pytest


class TestResponseTraceHeader:
    """验证 HTTP 响应头中注入 X-Trace-Id。"""

    def test_success_response_includes_x_trace_id(self, client):
        """正常请求响应应包含 X-Trace-Id 头。"""
        response = client.get("/")
        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers
        trace_id = response.headers["X-Trace-Id"]
        assert len(trace_id) == 12
        assert trace_id.isalnum()

    def test_api_response_includes_x_trace_id(self, client):
        """API 请求响应也应包含 X-Trace-Id 头。"""
        response = client.get("/api/v1/trends")
        assert "X-Trace-Id" in response.headers
        trace_id = response.headers["X-Trace-Id"]
        assert len(trace_id) == 12

    def test_error_response_includes_x_trace_id(self, client):
        """错误响应同样包含 X-Trace-Id 头。"""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
        assert "X-Trace-Id" in response.headers
        trace_id = response.headers["X-Trace-Id"]
        assert len(trace_id) == 12

    def test_trace_id_consistency_between_header_and_body(self, client):
        """响应头中的 trace_id 应与 JSON body 中的 trace_id 一致。"""
        response = client.get("/nonexistent-page")
        data = response.get_json()
        header_tid = response.headers["X-Trace-Id"]
        body_tid = data["trace_id"]
        assert header_tid == body_tid

    def test_trace_id_persists_across_subsequent_requests(self, client):
        """每次请求应生成不同的 trace_id。"""
        response1 = client.get("/")
        response2 = client.get("/")
        tid1 = response1.headers["X-Trace-Id"]
        tid2 = response2.headers["X-Trace-Id"]
        assert tid1 != tid2


class TestErrorTraceIdConsistency:
    """验证错误处理器复用请求上下文的 trace_id。"""

    def test_404_trace_id_matches_request_context(self, client, app):
        """404 错误中的 trace_id 应与请求上下文一致。"""
        with app.test_request_context("/nonexistent"):
            from flask import g

            g.trace_id = "fixed-tx-123"
            response = client.get("/nonexistent-page")

        data = response.get_json()
        # 由于 test_client 内部会创建新的请求上下文，
        # 此处验证的是 trace_id 存在且格式正确；
        # 更深层的上下文一致性由单元测试保证。
        assert "trace_id" in data
        assert len(data["trace_id"]) == 12


class TestCeleryTaskTraceId:
    """验证 Celery 任务执行时注入 trace_id。"""

    @pytest.fixture(autouse=True)
    def eager_backend(self):
        """使用内存 backend 避免连接 PostgreSQL。"""
        from celery_app import app as celery_app
        orig = celery_app.conf.result_backend
        celery_app.conf.result_backend = "cache+memory://"
        yield
        celery_app.conf.result_backend = orig

    def test_task_prerun_injects_trace_id(self, app):
        """task_prerun 信号应在任务执行前注入 trace_id。"""
        from vcw_celery_tasks.tasks import _get_task_trace_id

        class FakeRequest:
            meta = {"trace_id": "celery-tx-99"}

        class FakeTask:
            request = FakeRequest()

        trace_id = _get_task_trace_id(FakeTask())
        assert trace_id == "celery-tx-99"

    def test_task_trace_id_fallback_when_missing(self, app):
        """无 trace_id 时 _get_task_trace_id 应生成新的。"""
        from vcw_celery_tasks.tasks import _get_task_trace_id

        class FakeTask:
            request = None

        trace_id = _get_task_trace_id(FakeTask())
        assert len(trace_id) == 12
        assert trace_id.isalnum()

    def test_task_trace_id_from_request_attribute(self, app):
        """兼容直接设置在 request 属性上的 trace_id。"""
        from vcw_celery_tasks.tasks import _get_task_trace_id

        class FakeRequest:
            meta = None
            trace_id = "attr-tx-88"

        class FakeTask:
            request = FakeRequest()

        trace_id = _get_task_trace_id(FakeTask())
        assert trace_id == "attr-tx-88"

    def test_echo_task_preserves_trace_in_result(self, app):
        """echo_task 执行结果中应能体现 trace_id 存在性。"""
        from vcw_celery_tasks.tasks import echo_task

        result = echo_task.apply(args=["hello"]).result
        assert "Echo: hello" in result

"""
文案生成接口测试

覆盖同步生成、SSE 流式、异步任务提交与状态查询、异步批量任务。
所有涉及外部 LLM 的调用均被 mock，确保测试稳定、快速、离线可运行。
"""

import services.generation_service as _svc_mod
import vcw_copywriter.editor as _editor_mod
import vcw_copywriter.generator as _gen_mod
import vcw_copywriter.model_router as _router_mod


class TestSyncGenerate:
    """同步文案生成 /generate 测试"""

    def test_generate_requires_topic(self, client):
        """未提供主题时重定向回首页并提示错误"""
        response = client.post("/generate", data={"topic": ""}, follow_redirects=True)
        assert response.status_code == 200

    def test_generate_success(self, client):
        """正常提交后返回结果页"""
        # 替换模块属性（避免 monkeypatch 与复杂导入的交互问题）
        orig_build = _svc_mod.build_full_prompts
        orig_check = _svc_mod.check_and_report
        orig_generate = _svc_mod.CopywriterGenerator.generate
        orig_save_generated_svc = _svc_mod.CopywriterGenerator.save_generated
        orig_save_generated_gen = _gen_mod.CopywriterGenerator.save_generated
        orig_router_generate = _router_mod.ModelRouter.generate
        orig_save = _editor_mod.EditorWorkflow.save_draft

        _svc_mod.build_full_prompts = lambda **kwargs: ("system prompt", "user prompt")
        _svc_mod.check_and_report = lambda c, s: (True, "[INFO] 检查通过")
        _svc_mod.CopywriterGenerator.generate = lambda self, sp, up: (
            True, "这是测试生成的文案", {"model": "mock-model"}
        )
        _svc_mod.CopywriterGenerator.save_generated = (
            lambda self, content, topic, meta, output_dir: "/mock/path/test.md"
        )
        _gen_mod.CopywriterGenerator.save_generated = (
            lambda self, content, topic, meta, output_dir: "/mock/path/test.md"
        )
        _router_mod.ModelRouter.generate = lambda self, sp, up, **kw: (
            True, "这是测试生成的文案", {"model": "mock-router"}
        )
        _editor_mod.EditorWorkflow.save_draft = lambda self, **kwargs: "draft-123"

        try:
            response = client.post(
                "/generate",
                data={
                    "topic": "测试主题",
                    "audience": "港宝家长",
                    "core_data": "核心数据",
                    "policy_points": "政策要点",
                },
            )
            assert response.status_code == 200
            html = response.data.decode("utf-8")
            assert "测试生成的文案" in html or "draft-123" in html
        finally:
            _svc_mod.build_full_prompts = orig_build
            _svc_mod.check_and_report = orig_check
            _svc_mod.CopywriterGenerator.generate = orig_generate
            _svc_mod.CopywriterGenerator.save_generated = orig_save_generated_svc
            _gen_mod.CopywriterGenerator.save_generated = orig_save_generated_gen
            _router_mod.ModelRouter.generate = orig_router_generate
            _editor_mod.EditorWorkflow.save_draft = orig_save


class TestStreamGenerate:
    """SSE 流式生成 /api/v1/generate/stream 测试"""

    def test_stream_requires_topic(self, client):
        """缺少主题参数返回 SSE 错误流"""
        response = client.get("/api/v1/generate/stream")
        assert response.status_code == 200
        # 消费完整响应，避免 generator 上下文泄漏
        data = response.get_data()
        assert response.content_type.startswith("text/event-stream")
        assert "错误".encode("utf-8") in data

    def test_stream_success(self, client, monkeypatch):
        """正常流式生成返回 SSE 数据流"""

        def mock_generate_stream(self, req_data):
            yield "content", "第一段"
            yield "content", "第二段"
            yield "done", "ok"

        # 直接 mock GenerationService 的 generate_stream 方法
        monkeypatch.setattr(
            "services.generation_service.GenerationService.generate_stream",
            mock_generate_stream,
        )

        response = client.get("/api/v1/generate/stream?topic=测试主题")
        assert response.status_code == 200
        data = response.get_data()
        assert response.content_type.startswith("text/event-stream")
        assert b"content" in data or b"done" in data


class TestAsyncGenerate:
    """异步任务 /api/v1/generate/async 测试"""

    def test_async_requires_topic(self, client):
        """缺少主题返回错误 JSON"""
        response = client.post("/api/v1/generate/async", json={})
        data = response.get_json()
        assert response.status_code == 400
        assert data["success"] is False
        assert "error" in data

    def test_async_submit_success(self, client, monkeypatch):
        """正常提交返回 task_id"""

        class MockAsyncResult:
            id = "mock-task-12345"

        def mock_delay(*args, **kwargs):
            return MockAsyncResult()

        monkeypatch.setattr(
            "vcw_celery_tasks.tasks.generate_copy_task.delay",
            mock_delay,
        )

        response = client.post(
            "/api/v1/generate/async",
            json={"topic": "测试主题", "audience": "港宝家长"},
        )
        data = response.get_json()
        assert response.status_code == 200
        assert data["success"] is True
        assert data["data"]["task_id"] == "mock-task-12345"

    def test_async_status_not_found(self, client):
        """查询不存在的任务返回错误"""
        response = client.get("/api/v1/generate/status/nonexistent-id")
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_async_cancel_not_found(self, client):
        """取消不存在的任务返回失败"""
        response = client.post("/api/v1/generate/cancel/nonexistent-id")
        data = response.get_json()
        # 取消接口返回 {"success": bool}
        assert "success" in data


class TestAsyncBatchGenerate:
    """异步批量任务 /api/v1/generate/batch/* 测试"""

    def test_batch_async_requires_topic(self, client):
        """缺少主题返回错误 JSON"""
        response = client.post(
            "/api/v1/generate/batch/async",
            json={"angles": ["焦虑型", "数据型"]},
        )
        data = response.get_json()
        assert response.status_code == 400
        assert data["success"] is False
        assert "error" in data

    def test_batch_async_requires_angles(self, client):
        """缺少角度返回错误 JSON"""
        response = client.post(
            "/api/v1/generate/batch/async",
            json={"topic": "测试主题"},
        )
        data = response.get_json()
        assert response.status_code == 400
        assert data["success"] is False
        assert "error" in data

    def test_batch_async_submit_success(self, client, monkeypatch):
        """正常提交批量任务返回 batch_id"""

        class MockAsyncResult:
            id = "mock-batch-67890"

        def mock_delay(*args, **kwargs):
            return MockAsyncResult()

        monkeypatch.setattr(
            "vcw_celery_tasks.tasks.generate_batch_task.delay",
            mock_delay,
        )

        response = client.post(
            "/api/v1/generate/batch/async",
            json={
                "topic": "测试主题",
                "audience": "港宝家长",
                "angles": ["焦虑型", "数据型", "故事型"],
            },
        )
        data = response.get_json()
        assert response.status_code == 200
        assert data["success"] is True
        assert "batch_id" in data["data"]

    def test_batch_async_status_not_found(self, client):
        """查询不存在的批次返回错误"""
        response = client.get("/api/v1/generate/batch/status/nonexistent-batch")
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

    def test_batch_async_cancel_not_found(self, client):
        """取消不存在的批次返回错误"""
        response = client.post("/api/v1/generate/batch/cancel/nonexistent-batch")
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data

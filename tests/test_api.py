"""
视图函数测试示例（API v1）

测试策略：
  1. 使用 Flask test_client 发送真实 HTTP 请求。
  2. 通过 monkeypatch 替换外部依赖（DI 容器、模块级导入函数），
     使测试聚焦在视图层的请求/响应逻辑上。
  3. 禁止修改业务代码，所有隔离通过 mock 完成。
"""

from unittest.mock import MagicMock


class TestPromptsPreview:
    """测试 POST /api/v1/prompts/preview —— Prompt 预览接口"""

    def test_prompts_preview_success(self, client, monkeypatch):
        """
        正常场景：提供完整参数，期望返回 system/user prompt 的长度和预览。
        """
        mock_prompt_handler = MagicMock()
        mock_prompt_handler.handle_preview.return_value = {
            "system_length": 42,
            "user_length": 24,
            "system_preview": "系统提示预览",
            "user_preview": "用户提示预览",
        }
        monkeypatch.setattr(
            "app.api.v1.prompts.get_service",
            lambda name: mock_prompt_handler if name == "prompt_handler" else MagicMock(),
        )

        payload = {
            "topic": "DSE考砸后的保底路径",
            "audience": "港宝家长",
            "core_data": "DSE 2025年报考人数约5万人",
            "policy_points": "副学士六科全2分可读",
            "hidden_path": "英国部分大学接受DSE英文2分",
            "call_to_action": "留言领取升学路径全图",
        }

        resp = client.post("/api/v1/prompts/preview", json=payload)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "data" in data
        assert data["error"] is None

        # 验证返回的数据结构
        result = data["data"]
        assert "system_length" in result
        assert "user_length" in result
        assert "system_preview" in result
        assert "user_preview" in result
        assert result["system_length"] > 0
        assert result["user_length"] > 0

        # 验证 handler 方法被正确调用
        mock_prompt_handler.handle_preview.assert_called_once()
        call_args = mock_prompt_handler.handle_preview.call_args[0][0]
        assert call_args.data["topic"] == "DSE考砸后的保底路径"

    def test_prompts_preview_uses_defaults(self, client, monkeypatch):
        """
        默认参数场景：请求体为空，视图应使用模块默认值并正确渲染。
        """
        mock_prompt_handler = MagicMock()
        mock_prompt_handler.handle_preview.return_value = {
            "system_length": 10,
            "user_length": 10,
            "system_preview": "默认系统提示",
            "user_preview": "默认用户提示",
        }
        monkeypatch.setattr(
            "app.api.v1.prompts.get_service",
            lambda name: mock_prompt_handler if name == "prompt_handler" else MagicMock(),
        )

        resp = client.post("/api/v1/prompts/preview", json={})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["system_preview"].startswith("默认系统提示")

    def test_prompts_preview_service_failure(self, client, monkeypatch):
        """
        异常场景：prompt_handler.handle_preview 抛出异常，
        视图应在 try/except 中捕获并返回 error_response 结构。
        """
        mock_prompt_handler = MagicMock()
        mock_prompt_handler.handle_preview.side_effect = RuntimeError("DB connection lost")
        monkeypatch.setattr(
            "app.api.v1.prompts.get_service",
            lambda name: mock_prompt_handler if name == "prompt_handler" else MagicMock(),
        )

        resp = client.post("/api/v1/prompts/preview", json={"topic": "test"})

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert data["data"] is None
        assert data["error"]["code"] == "PREVIEW_FAILED"
        assert "DB connection lost" in data["error"]["message"]


class TestPromptsSave:
    """测试 POST /api/v1/prompts —— Prompt 保存接口"""

    def test_prompts_save_success(self, client, monkeypatch):
        """正常保存自定义 System Prompt"""
        mock_prompt_handler = MagicMock()
        monkeypatch.setattr(
            "app.api.v1.prompts.get_service",
            lambda name: mock_prompt_handler if name == "prompt_handler" else MagicMock(),
        )

        resp = client.post("/api/v1/prompts", json={"system_prompt": "new_template"})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        mock_prompt_handler.handle_save_system_template.assert_called_once()
        call_args = mock_prompt_handler.handle_save_system_template.call_args[0][0]
        assert call_args.system_prompt == "new_template"

    def test_prompts_save_empty_prompt(self, client):
        """空 Prompt 应返回 400 错误"""
        resp = client.post("/api/v1/prompts", json={"system_prompt": "   "})

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert data["error"]["code"] == "EMPTY_PROMPT"

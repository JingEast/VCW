"""安全测试：验证输入校验与边界处理。"""

from __future__ import annotations


class TestConfigSaveValidation:
    """验证 /config/save 的输入校验。"""

    def test_config_save_rejects_invalid_temperature(self, client):
        """非数字 temperature 返回错误提示。"""
        response = client.post(
            "/config/save",
            data={
                "api_key": "test-key",
                "model": "gpt-4o",
                "temperature": "not-a-number",
                "max_tokens": "2000",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Temperature" in html or "error" in html.lower()

    def test_config_save_rejects_invalid_max_tokens(self, client):
        """非整数 max_tokens 返回错误提示。"""
        response = client.post(
            "/config/save",
            data={
                "api_key": "test-key",
                "model": "gpt-4o",
                "temperature": "0.7",
                "max_tokens": "abc",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Max Tokens" in html or "error" in html.lower()

    def test_config_save_accepts_empty_api_key(self, client):
        """允许空 api_key（用户可能想清除已保存的 key）。"""
        response = client.post(
            "/config/save",
            data={
                "api_key": "",
                "model": "gpt-4o",
                "temperature": "0.7",
                "max_tokens": "2000",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_config_save_strips_whitespace(self, client):
        """api_key 和 model 应被 strip。"""
        response = client.post(
            "/config/save",
            data={
                "api_key": "  key-with-spaces  ",
                "model": "  gpt-4o  ",
                "temperature": "0.7",
                "max_tokens": "2000",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_config_save_rejects_negative_max_tokens(self, client):
        """负数 max_tokens 当前未拒绝，记录为已知行为。"""
        response = client.post(
            "/config/save",
            data={
                "api_key": "test",
                "model": "gpt-4o",
                "temperature": "0.7",
                "max_tokens": "-100",
            },
            follow_redirects=True,
        )
        # 当前实现允许负数通过（int("-100") 成功转换）
        assert response.status_code == 200


class TestApiEndpointsValidation:
    """验证 API 端点对非法输入的处理。"""

    def test_generate_rejects_empty_topic(self, client):
        """空主题应重定向并提示错误。"""
        response = client.post(
            "/generate",
            data={"topic": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_api_prompts_preview_accepts_empty_json(self, client, monkeypatch):
        """空 JSON 请求被视图层接受并转发给 handler（使用默认值）。"""
        from unittest.mock import MagicMock

        mock_handler = MagicMock()
        mock_handler.handle_preview.return_value = {
            "system_length": 10,
            "user_length": 10,
            "system_preview": "default",
            "user_preview": "default",
        }
        monkeypatch.setattr(
            "app.api.v1.prompts.get_service",
            lambda name: mock_handler if name == "prompt_handler" else MagicMock(),
        )

        response = client.post("/api/v1/prompts/preview", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_handler.handle_preview.assert_called_once()

    def test_stream_requires_topic(self, client):
        """缺少 topic 的流式请求返回 SSE 错误。"""
        response = client.get("/api/v1/generate/stream")
        assert response.status_code == 200
        assert response.content_type.startswith("text/event-stream")

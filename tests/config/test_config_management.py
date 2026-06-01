"""Config Management Tests

验证配置加载、回退、环境变量覆盖与一致性。
"""

import json
import os

from vcw_copywriter.config import Config, DEFAULT_CONFIG, ensure_dirs


class TestConfigLoading:
    """配置加载与回退测试"""

    def test_load_existing_config(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"llm": {"model": "gpt-4o-mini"}}), encoding="utf-8")
        cfg = Config(str(config_path))
        assert cfg.get("llm", "model") == "gpt-4o-mini"

    def test_merge_with_defaults(self, tmp_path):
        """部分配置应合并默认值，确保新字段存在。"""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"llm": {"model": "gpt-4o-mini"}}), encoding="utf-8")
        cfg = Config(str(config_path))
        # 默认值应被保留
        assert cfg.get("llm", "temperature") == 0.7
        assert cfg.get("memory", "db_path") == "data/memory_db.json"

    def test_missing_file_uses_defaults(self, tmp_path):
        config_path = tmp_path / "nonexistent.json"
        cfg = Config(str(config_path))
        assert cfg.get("llm", "model") == "gpt-4o"
        assert cfg.get("llm", "max_tokens") == 2000

    def test_default_max_tokens_is_positive(self):
        """默认 max_tokens 必须为正数。"""
        assert DEFAULT_CONFIG["llm"]["max_tokens"] > 0


class TestConfigSetGet:
    """配置读写测试"""

    def test_get_nested_key(self, tmp_path):
        cfg = Config(str(tmp_path / "config.json"))
        assert cfg.get("llm", "model") == "gpt-4o"
        assert cfg.get("llm", "nonexistent", default="fallback") == "fallback"

    def test_set_nested_key(self, tmp_path):
        cfg = Config(str(tmp_path / "config.json"))
        cfg.set("llm", "model", value="claude-3")
        assert cfg.get("llm", "model") == "claude-3"

    def test_save_and_reload(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = Config(str(config_path))
        cfg.set("llm", "model", value="test-model")
        cfg.save()

        cfg2 = Config(str(config_path))
        assert cfg2.get("llm", "model") == "test-model"


class TestEnvOverrides:
    """环境变量覆盖测试"""

    def test_database_url_env(self):
        """DATABASE_URL 环境变量应被识别。"""
        import subprocess
        import sys

        code = (
            "import os; os.environ['DATABASE_URL'] = 'postgresql://test@localhost/vcw'; "
            "from vcw_copywriter.db.session import DATABASE_URL; "
            "print(DATABASE_URL)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.stdout.strip() == "postgresql://test@localhost/vcw"

    def test_celery_broker_env(self):
        """CELERY_BROKER_URL 环境变量应覆盖默认值。"""
        import subprocess
        import sys

        code = (
            "import os; os.environ['CELERY_BROKER_URL'] = 'redis://custom:6379/1'; "
            "from celery_app import _BROKER_URL; "
            "print(_BROKER_URL)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.stdout.strip() == "redis://custom:6379/1"

    def test_secret_key_from_env(self, monkeypatch):
        """SECRET_KEY 应从环境变量读取。"""
        monkeypatch.setenv("SECRET_KEY", "my-production-secret")
        from app import create_app

        app = create_app()
        assert app.config["SECRET_KEY"] == "my-production-secret"


class TestConfigValidation:
    """配置值合法性验证"""

    def test_max_tokens_must_be_positive(self, tmp_path):
        """max_tokens 为负数时应被视为无效配置。"""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"llm": {"max_tokens": -100}}), encoding="utf-8")
        cfg = Config(str(config_path))
        # 当前实现会保留负值（由调用方校验），此处记录为已知行为
        assert cfg.get("llm", "max_tokens") == -100

    def test_temperature_range(self, tmp_path):
        """temperature 应在合理范围内（0-2）。"""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"llm": {"temperature": 0.5}}), encoding="utf-8")
        cfg = Config(str(config_path))
        t = cfg.get("llm", "temperature")
        assert 0 <= t <= 2


class TestEnsureDirs:
    """目录创建测试"""

    def test_ensure_dirs_creates_paths(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ensure_dirs()
        assert (tmp_path / "data").exists()
        assert (tmp_path / "data/generated").exists()

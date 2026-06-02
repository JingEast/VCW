"""安全测试：验证 AppSettings 配置 Schema 与启动校验。"""

from __future__ import annotations

import pytest


class TestAppSettingsValidation:
    """验证 AppSettings 字段校验。"""

    def test_secret_key_required_in_production(self, monkeypatch):
        """生产环境（非 TESTING、非 DEBUG）缺少 SECRET_KEY 应产生警告。"""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
        from app.core.config_schema import AppSettings, validate_startup_config

        # AppSettings 本身允许空 secret_key（不阻塞启动）
        settings = AppSettings()
        assert settings.secret_key == ""
        # 启动校验应检测到问题
        warnings = validate_startup_config()
        assert any("SECRET_KEY" in w for w in warnings)

    def test_secret_key_optional_when_testing(self, monkeypatch):
        """测试环境 SECRET_KEY 可选。"""
        monkeypatch.setenv("TESTING", "1")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        from app.core.config_schema import AppSettings

        settings = AppSettings()
        assert settings.secret_key == ""

    def test_database_url_must_be_valid(self, monkeypatch):
        """DATABASE_URL 必须是有效的数据库 URL。"""
        monkeypatch.setenv("DATABASE_URL", "invalid://foo")
        monkeypatch.setenv("TESTING", "1")
        from app.core.config_schema import AppSettings

        with pytest.raises(ValueError, match="DATABASE_URL"):
            AppSettings()

    def test_database_url_accepts_sqlite(self, monkeypatch):
        """允许 sqlite:// 前缀。"""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        monkeypatch.setenv("TESTING", "1")
        from app.core.config_schema import AppSettings

        settings = AppSettings()
        assert settings.database_url == "sqlite:///test.db"

    def test_pool_size_within_range(self, monkeypatch):
        """db_pool_size 必须在 1-100 范围内。"""
        monkeypatch.setenv("DB_POOL_SIZE", "150")
        monkeypatch.setenv("TESTING", "1")
        from app.core.config_schema import AppSettings

        with pytest.raises(ValueError):
            AppSettings()

    def test_safe_dict_masks_api_key(self, monkeypatch):
        """to_safe_dict 应脱敏 API Key。"""
        monkeypatch.setenv("VCW_API_KEY", "sk-abcdef1234567890")
        monkeypatch.setenv("TESTING", "1")
        from app.core.config_schema import AppSettings

        settings = AppSettings()
        safe = settings.to_safe_dict()
        assert "****" in safe["vcw_api_key"]
        # 脱敏后保留前4后4，中间替换为 ****
        assert safe["vcw_api_key"].startswith("sk-a")
        assert safe["vcw_api_key"].endswith("7890")


class TestStartupValidation:
    """验证启动时校验逻辑。"""

    def test_validate_startup_warns_about_sqlite_in_production(self, monkeypatch):
        """生产环境使用 SQLite 应产生警告。"""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///data/vcw.db")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.delenv("FLASK_DEBUG", raising=False)
        monkeypatch.delenv("TESTING", raising=False)
        from app.core.config_schema import validate_startup_config

        warnings = validate_startup_config()
        assert any("SQLite" in w for w in warnings)

    def test_validate_startup_warns_about_debug_mode(self, monkeypatch):
        """DEBUG 模式应产生警告。"""
        monkeypatch.setenv("FLASK_DEBUG", "true")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.delenv("TESTING", raising=False)
        from app.core.config_schema import validate_startup_config

        warnings = validate_startup_config()
        assert any("debug" in w.lower() for w in warnings)

    def test_validate_startup_warns_about_missing_api_key(self, monkeypatch):
        """缺少 API Key 应产生警告。"""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key")
        monkeypatch.delenv("VCW_API_KEY", raising=False)
        monkeypatch.delenv("TESTING", raising=False)
        from app.core.config_schema import validate_startup_config

        warnings = validate_startup_config()
        assert any("API_KEY" in w for w in warnings)

"""应用配置 Schema 与启动校验。

使用 pydantic Settings 统一管理环境变量：
  - 启动时自动校验类型与必填项
  - 生产环境强制检测关键配置
  - 敏感字段自动脱敏日志输出
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AppSettings(BaseSettings):
    """应用配置定义（从环境变量加载）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Flask
    secret_key: str = Field(default="", description="Flask SECRET_KEY")
    flask_debug: bool = Field(default=False, description="Flask DEBUG 模式")

    # Database
    database_url: str = Field(
        default="sqlite:///data/vcw.db",
        description="数据库连接 URL",
    )
    db_pool_size: int = Field(default=10, ge=1, le=100, description="连接池大小")
    db_max_overflow: int = Field(default=20, ge=0, le=200, description="连接池溢出上限")

    # LLM
    vcw_api_key: str = Field(default="", description="LLM API Key")
    vcw_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="LLM Base URL",
    )
    vcw_model: str = Field(default="gpt-4o", description="默认模型")

    # Celery
    celery_broker_url: Optional[str] = Field(default=None, description="Celery Broker URL")
    celery_result_backend: Optional[str] = Field(default=None, description="Celery Result Backend")

    # Cache / CORS
    redis_url: Optional[str] = Field(default=None, description="Redis URL（用于 Flask-Caching）")
    cors_origins: str = Field(
        default="http://localhost:5000,http://127.0.0.1:5000",
        description="CORS 允许来源（逗号分隔）",
    )

    @field_validator("secret_key")
    @classmethod
    def _check_secret_key_in_production(cls, v: str) -> str:
        if not v and not os.environ.get("TESTING") and not os.environ.get("FLASK_DEBUG"):
            logger.warning(
                "SECRET_KEY is not set in production environment. "
                "Please set the SECRET_KEY environment variable."
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, v: str) -> str:
        if not v.startswith(("sqlite://", "postgresql://", "postgresql+psycopg2://")):
            raise ValueError(
                "DATABASE_URL must start with sqlite://, postgresql:// or postgresql+psycopg2://"
            )
        return v

    def to_safe_dict(self) -> dict[str, str | int | bool | None]:
        """导出脱敏后的配置字典（用于日志）。"""
        return {
            "flask_debug": self.flask_debug,
            "database_url": self._mask_url(self.database_url),
            "db_pool_size": self.db_pool_size,
            "db_max_overflow": self.db_max_overflow,
            "vcw_base_url": self.vcw_base_url,
            "vcw_model": self.vcw_model,
            "vcw_api_key": self._mask_secret(self.vcw_api_key),
            "celery_broker_url": self._mask_url(self.celery_broker_url or ""),
            "celery_result_backend": self._mask_url(self.celery_result_backend or ""),
            "redis_url": self._mask_url(self.redis_url or ""),
            "cors_origins": self.cors_origins,
        }

    @staticmethod
    def _mask_secret(value: str) -> str:
        if len(value) <= 8:
            return "***" if value else ""
        return value[:4] + "****" + value[-4:]

    @staticmethod
    def _mask_url(value: str) -> str:
        """脱敏 URL 中的密码部分。"""
        if "@" not in value:
            return value
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(value)
            if parsed.password:
                netloc = parsed.netloc.replace(
                    f":{parsed.password}@", ":****@"
                )
                return urlunparse(parsed._replace(netloc=netloc))
        except Exception:
            pass
        return value


_settings: Optional[AppSettings] = None


def load_settings() -> AppSettings:
    """加载并校验应用配置。

    首次调用时从环境变量构建 Settings 实例，后续返回缓存。
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def get_settings() -> AppSettings:
    """获取当前 Settings 实例（必须先调用 load_settings）。"""
    if _settings is None:
        raise RuntimeError("Settings not loaded. Call load_settings() first.")
    return _settings


def validate_startup_config() -> list[str]:
    """启动时执行额外校验，返回警告列表。

    若配置校验失败，将错误信息作为警告返回，不阻止应用启动。
    """
    warnings: list[str] = []
    try:
        # 使用新实例以支持测试环境动态修改环境变量
        settings = AppSettings()
    except Exception as e:
        warnings.append(f"Configuration validation failed: {e}")
        return warnings

    if not settings.secret_key:
        warnings.append("SECRET_KEY is not set. Sessions will be invalidated across restarts.")

    is_testing = os.environ.get("TESTING") is not None
    if settings.flask_debug and not is_testing:
        warnings.append("FLASK_DEBUG is enabled. Do not use debug mode in production.")

    if settings.database_url.startswith("sqlite://") and not settings.flask_debug:
        warnings.append("Using SQLite in production is not recommended. Consider PostgreSQL.")

    if not settings.vcw_api_key:
        warnings.append("VCW_API_KEY is not set. LLM generation will fail.")

    return warnings

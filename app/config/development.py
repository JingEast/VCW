"""Development Configuration."""

from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development environment settings."""

    DEBUG = True
    FLASK_DEBUG = True

    # Relaxed session security for local dev
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

    # SQLite for quick local development
    SQLALCHEMY_DATABASE_URI = "sqlite:///data/vcw_dev.db"

    # Shorter JWT expiry for testing
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES = 60

    # Verbose logging
    LOG_LEVEL = "DEBUG"

    # Backup
    BACKUP_DIR = "data/backups"
    BACKUP_RETENTION_DAYS = 3

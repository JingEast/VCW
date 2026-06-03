"""Production Configuration."""

import os

from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production environment settings."""

    DEBUG = False
    FLASK_DEBUG = False

    # Mandatory secrets check
    SECRET_KEY = os.environ["SECRET_KEY"]

    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]

    # Strict session security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Strict"

    # PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://vcw:vcw@localhost:5432/vcw",
    )

    # Celery with Redis
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND",
        "db+postgresql+psycopg2://vcw:vcw@localhost:5432/vcw",
    )

    # Production logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")

    # Rate limiting stricter in production
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # Backup
    BACKUP_DIR = os.environ.get("BACKUP_DIR", "data/backups")
    BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "7"))

"""Base Configuration.

Shared settings across all environments.
"""

import os
from datetime import timedelta


class BaseConfig:
    """Base Flask configuration."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    TESTING = False
    DEBUG = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///data/vcw.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # CORS
    CORS_ORIGINS = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000",
    )

    # LLM
    VCW_API_KEY = os.environ.get("VCW_API_KEY", "")
    VCW_BASE_URL = os.environ.get("VCW_BASE_URL", "https://api.openai.com/v1")
    VCW_MODEL = os.environ.get("VCW_MODEL", "gpt-4o")

    # Celery
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND",
        "db+sqlite:///data/celery_results.db",
    )

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

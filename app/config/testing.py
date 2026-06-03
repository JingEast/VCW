"""Testing Configuration."""

from .base import BaseConfig


class TestingConfig(BaseConfig):
    """Test environment settings."""

    TESTING = True
    DEBUG = True

    # In-memory SQLite for fast tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Disable CSRF for test client
    WTF_CSRF_ENABLED = False

    # Short-lived tokens
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES = 5

    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False

    # Test secret (predictable)
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret"

    # Backup (use temp dir in tests)
    BACKUP_DIR = "/tmp/vcw_test_backups"
    BACKUP_RETENTION_DAYS = 1

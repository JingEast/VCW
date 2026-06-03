"""Enhanced Logging Configuration.

Fixes Windows RotatingFileHandler WinError 32 by using
concurrent-log-handler for safe multi-process rotation.

Provides structured JSON logging with separated streams:
- access.log: HTTP requests
- error.log: Exceptions and errors
- security.log: Auth and security events
"""

import logging
import os

from flask import Flask

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_enhanced_logging(app: Flask) -> None:
    """Configure enhanced logging with separate streams."""
    log_dir = os.path.join(app.root_path, "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    level = LOG_LEVEL_MAP.get(os.environ.get("LOG_LEVEL", "INFO"), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-init
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(_json_formatter())
    root.addHandler(console)

    # Access log (all INFO+)
    access_path = os.path.join(log_dir, "access.log")
    access_handler = _safe_rotating_handler(access_path, level=logging.INFO)
    access_handler.setFormatter(_json_formatter())
    root.addHandler(access_handler)

    # Error log (ERROR+)
    error_path = os.path.join(log_dir, "error.log")
    error_handler = _safe_rotating_handler(error_path, level=logging.ERROR)
    error_handler.setFormatter(_json_formatter())
    root.addHandler(error_handler)

    # Security log (WARNING+)
    security_path = os.path.join(log_dir, "security.log")
    security_handler = _safe_rotating_handler(security_path, level=logging.WARNING)
    security_handler.setFormatter(_json_formatter())
    security_filter = _SecurityFilter()
    security_handler.addFilter(security_filter)
    root.addHandler(security_handler)

    app.logger.info(
        "Enhanced logging initialized: access=%s error=%s security=%s",
        access_path, error_path, security_path,
    )


def _safe_rotating_handler(path: str, level: int) -> logging.Handler:
    """Create a rotating file handler safe for Windows multi-process."""
    try:
        from concurrent_log_handler import ConcurrentRotatingFileHandler
        handler: logging.Handler = ConcurrentRotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    except ImportError:
        # Fallback to standard RotatingFileHandler (single-process only)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    handler.setLevel(level)
    return handler


def _json_formatter() -> logging.Formatter:
    """Return JSON formatter for structured logging."""
    from app.core.logging_config import JsonFormatter
    return JsonFormatter()


class _SecurityFilter(logging.Filter):
    """Filter security-related log records."""

    SECURITY_KEYWORDS = {"auth", "login", "logout", "jwt", "csrf", "token", "unauthorized", "forbidden"}

    def filter(self, record: logging.LogRecord) -> bool:
        message = f"{record.getMessage()} {getattr(record, 'funcName', '')}".lower()
        return any(kw in message for kw in self.SECURITY_KEYWORDS)

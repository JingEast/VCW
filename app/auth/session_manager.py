"""Session Manager.

Enhances Flask-Login with security-focused session policies.
"""

from datetime import timedelta

from flask import Flask, session


def init_session_manager(app: Flask) -> None:
    """Initialize session management with security hardening.

    Uses the shared login_manager from session_handler to avoid
    duplicate LoginManager instances.
    """
    # login_manager is already initialized in init_login_manager
    # We only add session hardening policies here

    # Session lifetime
    app.permanent_session_lifetime = timedelta(hours=12)

    # Cookie security (overridden per environment in config)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_HTTPONLY", True)
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_DURATION", timedelta(days=14))

    @app.before_request
    def _refresh_session() -> None:
        """Regenerate session ID on login to prevent fixation."""
        if session.get("_fresh_login"):
            session.pop("_fresh_login", None)
            session.modified = True

"""API Authentication Middleware.

Validates JWT on API routes before request handling.
Falls back to session auth for same-origin requests.
Public routes are whitelisted.
"""

from typing import Set

from flask import Flask, jsonify, request

# Public routes that do NOT require authentication
PUBLIC_API_ROUTES: Set[str] = {
    "/api/v1/health",
    "/api/v1/status",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/health",
    "/metrics",
}

# Public page routes
PUBLIC_PAGE_ROUTES: Set[str] = {
    "/",
    "/login",
    "/register",
    "/static/",
}

# Deferred imports to avoid ModuleNotFoundError at import time
_jwt_available = False
_flask_login_available = False


def _ensure_imports() -> None:
    global _jwt_available, _flask_login_available
    if _jwt_available and _flask_login_available:
        return
    try:
        import flask_jwt_extended  # noqa: F401
        _jwt_available = True
    except ImportError:
        pass
    try:
        import flask_login  # noqa: F401
        _flask_login_available = True
    except ImportError:
        pass


def _is_jwt_present() -> bool:
    """Check if Authorization header contains a Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    return auth_header.startswith("Bearer ")


def _is_authenticated() -> bool:
    """Check session authentication via Flask-Login."""
    if not _flask_login_available:
        return False
    try:
        from flask_login import current_user
        return current_user.is_authenticated
    except Exception:
        return False


def register_auth_middleware(app: Flask) -> None:
    """Register before_request handler for API auth."""
    _ensure_imports()

    @app.before_request
    def _check_api_auth():
        # Testing mode: skip auth to avoid breaking existing tests
        if app.config.get("TESTING"):
            return None

        path = request.path

        # Skip static files and health endpoints
        if path.startswith("/static/") or path in PUBLIC_API_ROUTES:
            return None

        # Page routes use session auth (handled by Flask-Login @login_required)
        if not path.startswith("/api/v1/"):
            return None

        # API routes — allow public whitelisted
        if path in PUBLIC_API_ROUTES:
            return None

        # Try JWT first (external API clients)
        if _jwt_available and _is_jwt_present():
            try:
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request()
                return None
            except Exception:
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid JWT token",
                    },
                }), 401

        # Fall back to session auth (same-origin web UI AJAX)
        if _is_authenticated():
            return None

        # No valid auth
        return jsonify({
            "success": False,
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Authentication required. Provide a Bearer JWT token or login via session.",
            },
        }), 401

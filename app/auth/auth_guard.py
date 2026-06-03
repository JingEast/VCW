"""Auth Guard — Unified authentication guard for pages and APIs.

Combines JWT (API) and Session (pages) checks with role-based access.
"""

from functools import wraps
from typing import Callable

from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request
from flask_login import current_user


def api_auth_required(fn: Callable) -> Callable:
    """Require JWT authentication for API endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return fn(*args, **kwargs)
        try:
            verify_jwt_in_request()
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": str(exc)},
            }), 401
        return fn(*args, **kwargs)
    return wrapper


def page_auth_required(fn: Callable) -> Callable:
    """Require session login for page endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            from flask import redirect, url_for
            return redirect(url_for("login", next=request.url))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn: Callable) -> Callable:
    """Require admin role (works for both JWT and Session)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # API path — check JWT role
        if request.path.startswith("/api/"):
            try:
                verify_jwt_in_request()
                from flask_jwt_extended import get_jwt
                role = get_jwt().get("role", "viewer")
            except Exception as exc:
                return jsonify({
                    "success": False,
                    "error": {"code": "UNAUTHORIZED", "message": str(exc)},
                }), 401
        else:
            # Page path — check session role
            if not current_user.is_authenticated:
                from flask import redirect, url_for
                return redirect(url_for("login", next=request.url))
            role = getattr(current_user, "role", "viewer")

        if role != "admin":
            return jsonify({
                "success": False,
                "error": {"code": "FORBIDDEN", "message": "需要管理员权限"},
            }), 403

        return fn(*args, **kwargs)
    return wrapper

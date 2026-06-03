"""Authentication Decorators.

Provides @jwt_required_custom, @login_required_custom, @require_role.
"""

from functools import wraps
from typing import Callable

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_login import current_user


def jwt_required_custom(fn: Callable) -> Callable:
    """Decorator to require valid JWT on API endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": str(exc)},
            }), 401
        return fn(*args, **kwargs)
    return wrapper


def login_required_custom(fn: Callable) -> Callable:
    """Decorator to require session login on page endpoints."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                "success": False,
                "error": {"code": "LOGIN_REQUIRED", "message": "请先登录"},
            }), 401
        return fn(*args, **kwargs)
    return wrapper


def require_role(role: str):
    """Decorator factory to require specific role (admin/editor/viewer)."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                from flask_jwt_extended import get_jwt
                user_role = get_jwt().get("role", "viewer")
                if user_role != role:
                    return jsonify({
                        "success": False,
                        "error": {"code": "FORBIDDEN", "message": f"需要 {role} 权限"},
                    }), 403
            except Exception as exc:
                return jsonify({
                    "success": False,
                    "error": {"code": "UNAUTHORIZED", "message": str(exc)},
                }), 401
            return fn(*args, **kwargs)
        return wrapper
    return decorator

"""VCW Authentication Module.

Provides JWT and Session-based authentication.
P0 security hardening for PO-07.
"""

# Lazy imports to avoid ModuleNotFoundError when optional deps are missing

__all__ = ["jwt_manager", "init_jwt", "login_manager", "init_login_manager"]


class _LazyJWTManager:
    """Lazy proxy for JWTManager that imports on first access."""
    _instance = None

    def __getattr__(self, name: str):
        if self._instance is None:
            from flask_jwt_extended import JWTManager
            self._instance = JWTManager()
        return getattr(self._instance, name)


class _LazyLoginManager:
    """Lazy proxy for LoginManager that imports on first access."""
    _instance = None

    def __getattr__(self, name: str):
        if self._instance is None:
            from flask_login import LoginManager
            self._instance = LoginManager()
        return getattr(self._instance, name)


try:
    from .jwt_handler import jwt_manager, init_jwt
except ImportError:
    jwt_manager = _LazyJWTManager()  # type: ignore[assignment]

    def init_jwt(app):  # type: ignore[misc]
        raise RuntimeError("flask-jwt-extended not installed")

try:
    from .session_handler import login_manager, init_login_manager
except ImportError:
    login_manager = _LazyLoginManager()  # type: ignore[assignment]

    def init_login_manager(app):  # type: ignore[misc]
        raise RuntimeError("flask-login not installed")

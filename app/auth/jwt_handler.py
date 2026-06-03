"""JWT Authentication Handler.

Provides JWT token creation, validation and refresh.
Integrates with Flask-JWT-Extended.
"""

import os
from datetime import timedelta
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token

jwt_manager: JWTManager = JWTManager()


def init_jwt(app: Flask) -> None:
    """Initialize JWT extension on the Flask app."""
    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY",
        os.environ.get("SECRET_KEY", app.config.get("SECRET_KEY", "dev-jwt-key")),
    )
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30"))
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7"))
    )
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    jwt_manager.init_app(app)


def generate_tokens(user_id: str, role: str = "viewer") -> dict:
    """Generate access and refresh tokens for a user."""
    additional_claims = {"role": role}
    return {
        "access_token": create_access_token(identity=user_id, additional_claims=additional_claims),
        "refresh_token": create_refresh_token(identity=user_id, additional_claims=additional_claims),
        "token_type": "Bearer",
        "expires_in": 1800,  # 30 minutes in seconds
    }

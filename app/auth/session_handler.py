"""Session-based Authentication Handler.

Provides traditional session cookie login for page routes.
Integrates with Flask-Login.
"""

from flask import Flask
from flask_login import LoginManager

login_manager: LoginManager = LoginManager()


def init_login_manager(app: Flask) -> None:
    """Initialize Flask-Login on the app."""
    login_manager.init_app(app)
    login_manager.login_view = "login"  # type: ignore[assignment]
    login_manager.login_message = "请先登录以访问此页面。"
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id: str):
        """Load user by ID for Flask-Login session management."""
        from vcw_copywriter.db.session import get_session
        from vcw_copywriter.db.models import User
        session = get_session()
        try:
            user = session.query(User).filter_by(id=int(user_id)).first()
            return user
        finally:
            session.close()

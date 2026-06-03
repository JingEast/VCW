"""Authentication API endpoints (JWT + session)."""
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from flask_jwt_extended import create_access_token, create_refresh_token
    _jwt_available = True
except ImportError:
    _jwt_available = False

from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.models import User

bp = Blueprint("api_v1_auth", __name__)


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


@bp.route("/auth/login", methods=["POST"])
def api_login():
    """Authenticate and return JWT tokens."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "Username and password required"},
        }), 400
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": "Invalid username or password"},
            }), 401
        if not user.is_active:
            return jsonify({
                "success": False,
                "error": {"code": "FORBIDDEN", "message": "Account is disabled"},
            }), 403
        result = {
            "success": True,
            "data": {
                "user": _user_to_dict(user),
            },
        }
        if _jwt_available:
            user_id = str(user.id)
            additional_claims = {"role": user.role}
            result["data"]["access_token"] = create_access_token(identity=user_id, additional_claims=additional_claims)
            result["data"]["refresh_token"] = create_refresh_token(identity=user_id, additional_claims=additional_claims)
            result["data"]["token_type"] = "Bearer"
            result["data"]["expires_in"] = 1800
        return jsonify(result), 200
    finally:
        session.close()


@bp.route("/auth/register", methods=["POST"])
def api_register():
    """Register a new user account."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not username or not email or not password:
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "Username, email and password required"},
        }), 400
    if len(password) < 6:
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "Password must be at least 6 characters"},
        }), 400
    session = get_session()
    try:
        if session.query(User).filter_by(username=username).first():
            return jsonify({
                "success": False,
                "error": {"code": "CONFLICT", "message": "Username already exists"},
            }), 409
        if session.query(User).filter_by(email=email).first():
            return jsonify({
                "success": False,
                "error": {"code": "CONFLICT", "message": "Email already registered"},
            }), 409
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role="viewer",
            is_active=True,
        )
        session.add(user)
        session.commit()
        return jsonify({
            "success": True,
            "data": {"user": _user_to_dict(user)},
        }), 201
    finally:
        session.close()


@bp.route("/auth/me", methods=["GET"])
def api_me():
    """Return current authenticated user info."""
    # Try JWT first
    if _jwt_available:
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            verify_jwt_in_request()
            identity = get_jwt_identity()
            user_id = identity.get("user_id") if isinstance(identity, dict) else identity
            session = get_session()
            try:
                user = session.query(User).filter_by(id=int(user_id)).first()
                if user:
                    return jsonify({"success": True, "data": {"user": _user_to_dict(user)}}), 200
            finally:
                session.close()
        except Exception:
            pass
    # Fall back to session auth
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            return jsonify({"success": True, "data": {"user": _user_to_dict(current_user)}}), 200
    except Exception:
        pass
    return jsonify({
        "success": False,
        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated"},
    }), 401


@bp.route("/auth/refresh", methods=["POST"])
def api_refresh():
    """Refresh JWT access token."""
    if not _jwt_available:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_IMPLEMENTED", "message": "JWT not available"},
        }), 501
    try:
        from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request_refresh_token
        verify_jwt_in_request_refresh_token()
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "viewer")
        access_token = create_access_token(identity=user_id, additional_claims={"role": role})
        return jsonify({
            "success": True,
            "data": {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 1800,
            },
        }), 200
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": {"code": "UNAUTHORIZED", "message": str(exc)},
        }), 401

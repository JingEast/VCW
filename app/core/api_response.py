"""Standardized API Response Builder.

Provides uniform JSON response structure for all API endpoints.
"""

from typing import Any, Optional

from flask import jsonify


def success(
    data: Any = None,
    message: str = "ok",
    meta: Optional[dict] = None,
) -> tuple:
    """Build a successful API response."""
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "error": None,
    }
    if meta:
        payload["meta"] = meta
    return jsonify(payload), 200


def created(
    data: Any = None,
    message: str = "created",
) -> tuple:
    """Build a 201 Created response."""
    return jsonify({
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "error": None,
    }), 201


def accepted(
    data: Any = None,
    message: str = "accepted",
) -> tuple:
    """Build a 202 Accepted response."""
    return jsonify({
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "error": None,
    }), 202


def error(
    code: str = "INTERNAL_ERROR",
    message: str = "Internal Server Error",
    details: Any = None,
    status_code: int = 500,
) -> tuple:
    """Build an error API response."""
    return jsonify({
        "success": False,
        "message": message,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }), status_code


def bad_request(
    message: str = "Bad Request",
    details: Any = None,
) -> tuple:
    """Build a 400 Bad Request response."""
    return error("BAD_REQUEST", message, details, 400)


def unauthorized(
    message: str = "Unauthorized",
) -> tuple:
    """Build a 401 Unauthorized response."""
    return error("UNAUTHORIZED", message, None, 401)


def forbidden(
    message: str = "Forbidden",
) -> tuple:
    """Build a 403 Forbidden response."""
    return error("FORBIDDEN", message, None, 403)


def not_found(
    message: str = "Not Found",
) -> tuple:
    """Build a 404 Not Found response."""
    return error("NOT_FOUND", message, None, 404)

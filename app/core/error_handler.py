"""Global Error Handlers.

Provides uniform error responses for common HTTP exceptions.
Designed to be registered in Flask app error handlers.
"""

import traceback
from typing import Any

from flask import Flask, jsonify, request

from app.core.api_response import bad_request, error, forbidden, not_found, unauthorized


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers on the Flask app."""

    @app.errorhandler(400)
    def handle_bad_request(exc: Any):
        app.logger.warning("400 %s %s | %s", request.method, request.url, str(exc))
        return bad_request(getattr(exc, "description", str(exc)))

    @app.errorhandler(401)
    def handle_unauthorized(exc: Any):
        app.logger.warning("401 %s %s", request.method, request.url)
        return unauthorized(getattr(exc, "description", "Unauthorized"))

    @app.errorhandler(403)
    def handle_forbidden(exc: Any):
        app.logger.warning("403 %s %s", request.method, request.url)
        return forbidden(getattr(exc, "description", "Forbidden"))

    @app.errorhandler(404)
    def handle_not_found(exc: Any):
        app.logger.warning("404 %s %s", request.method, request.url)
        return not_found(getattr(exc, "description", "Not Found"))

    @app.errorhandler(405)
    def handle_method_not_allowed(exc: Any):
        app.logger.warning("405 %s %s", request.method, request.url)
        return error("METHOD_NOT_ALLOWED", "Method Not Allowed", None, 405)

    @app.errorhandler(429)
    def handle_rate_limit(exc: Any):
        app.logger.warning("429 %s %s", request.method, request.url)
        return error("RATE_LIMITED", "Too Many Requests", None, 429)

    @app.errorhandler(500)
    def handle_internal_error(exc: Any):
        app.logger.error("500 %s %s | %s\n%s", request.method, request.url, str(exc), traceback.format_exc())
        return error("INTERNAL_ERROR", "Internal Server Error", None, 500)

    @app.errorhandler(Exception)
    def handle_unhandled(exc: Exception):
        app.logger.error("UNHANDLED %s %s | %s\n%s", request.method, request.url, str(exc), traceback.format_exc())
        return error(
            "UNHANDLED_EXCEPTION",
            str(exc) if app.debug else "Internal Server Error",
            None,
            500,
        )

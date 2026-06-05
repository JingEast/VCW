"""VCW Middleware Module.

Provides request/response middleware for auth, logging, and security.
P0 security hardening for PO-07.
"""

from .auth_middleware import register_auth_middleware

__all__ = ["register_auth_middleware"]

"""Service provider interface for decoupling Celery tasks from app container.

This module provides a thin indirection so that vcw_celery_tasks (and other
low-level workers) can resolve services without importing app.core.container
directly, breaking the app -> domains -> services -> vcw_celery_tasks -> app
circular dependency.

Usage:
    # In app/core/container.py (during app init):
    from interfaces.service_provider import register_service_provider
    register_service_provider(get_service)

    # In vcw_celery_tasks/tasks.py:
    from interfaces.service_provider import get_service
    svc = get_service("generation_service")
"""

from __future__ import annotations

from typing import Any, Callable

_get_service_impl: Callable[[str], Any] | None = None


def register_service_provider(fn: Callable[[str], Any]) -> None:
    """Register the concrete service resolution function.

    Called once during application initialization.
    """
    global _get_service_impl
    _get_service_impl = fn


def get_service(name: str) -> Any:
    """Resolve a service by name from the registered provider.

    Raises:
        RuntimeError: If no provider has been registered.
        KeyError: If the service name is unknown.
    """
    if _get_service_impl is None:
        raise RuntimeError(
            "Service provider not registered. "
            "Ensure app.core.container.register_service_provider() is called during init."
        )
    return _get_service_impl(name)

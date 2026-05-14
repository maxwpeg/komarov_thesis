"""Request-scoped observability context."""

from __future__ import annotations

from contextvars import ContextVar, Token


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> Token[str | None]:
    """Set the request identifier for the current async context."""
    return request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Return the active request identifier, if any."""
    return request_id_var.get()


def reset_request_id(token: Token[str | None]) -> None:
    """Reset the request identifier to its previous value."""
    request_id_var.reset(token)

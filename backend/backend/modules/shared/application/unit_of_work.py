"""Shared transaction boundary abstractions."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session


class UnitOfWork(Protocol):
    """Minimal transaction boundary for application use cases."""

    session: Session

    def flush(self) -> None:
        """Flush staged changes to the persistence layer."""

    def commit(self) -> None:
        """Commit the current transaction."""

    def rollback(self) -> None:
        """Rollback the current transaction."""

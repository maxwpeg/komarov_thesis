"""Repository contracts for signal design."""

from __future__ import annotations

from typing import Protocol


class SignalDesignRepository(Protocol):
    """Persistence contract for signal design workflows."""

    def get_floor_plan(self, floor_plan_id: int):
        """Return a floor plan aggregate model."""

    def get_instrument(self, instrument_id: int):
        """Return a signal instrument model or raise."""

    def get_route(self, route_id: int):
        """Return a cable route model or raise."""

    def list_zones(self, floor_plan_id: int) -> list:
        """List zones for a floor plan."""

    def list_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list:
        """List signal instruments."""

    def list_routes(self, floor_plan_id: int, system_type: str | None = None) -> list:
        """List cable routes."""

    def list_fire_alarms(self, floor_plan_id: int, system_type: str | None = None) -> list:
        """List branch fire alarms."""

    def create_zone(self, data: dict):
        """Create a ZKSPC zone persistence entity."""

    def create_zone_room(self, zone_id: int, room_id: int):
        """Create a ZKSPC zone-room link."""

    def create_fire_alarm(self, data: dict):
        """Create a fire alarm persistence entity."""

    def create_instrument(self, data: dict):
        """Create a signal instrument persistence entity."""

    def create_route(self, data: dict):
        """Create a cable route persistence entity."""

    def add(self, entity) -> None:
        """Track an entity for persistence."""

    def delete(self, entity) -> None:
        """Delete an entity from persistence."""

    def flush(self) -> None:
        """Flush staged changes."""

    def refresh(self, entity) -> None:
        """Refresh an entity from persistence."""

    def delete_routes_for_instrument(self, instrument_id: int) -> None:
        """Delete persisted routes for one instrument."""

    def delete_routes_for_branch(self, floor_plan_id: int, system_type: str) -> None:
        """Delete persisted routes for one branch."""

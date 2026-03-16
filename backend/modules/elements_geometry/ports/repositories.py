"""Repository contracts for element geometry operations."""

from __future__ import annotations

from typing import Protocol


class ElementsRepository(Protocol):
    """Persistence contract for element geometry aggregates."""

    def get_floor_plan(self, floor_plan_id: int):
        """Return a floor plan model or raise."""

    def get_wall(self, wall_id: int):
        """Return a wall model or raise."""

    def get_door(self, door_id: int):
        """Return a door model or raise."""

    def get_window(self, window_id: int):
        """Return a window model or raise."""

    def get_stair(self, stair_id: int):
        """Return a stair model or raise."""

    def get_room(self, room_id: int):
        """Return a room model or raise."""

    def get_dimension(self, dimension_id: int):
        """Return a dimension model or raise."""

    def get_fire_alarm(self, fire_alarm_id: int):
        """Return a fire alarm model or raise."""

    def list_walls(self, floor_plan_id: int) -> list:
        """List walls for a floor plan."""

    def list_doors(self, floor_plan_id: int) -> list:
        """List doors for a floor plan."""

    def list_windows(self, floor_plan_id: int) -> list:
        """List windows for a floor plan."""

    def list_stairs(self, floor_plan_id: int) -> list:
        """List stairs for a floor plan."""

    def list_rooms(self, floor_plan_id: int) -> list:
        """List rooms for a floor plan."""

    def list_dimensions(self, floor_plan_id: int) -> list:
        """List dimensions for a floor plan."""

    def list_fire_alarms(self, floor_plan_id: int) -> list:
        """List fire alarms for a floor plan."""

    def list_zkspc_zones(self, floor_plan_id: int) -> list:
        """List ZKSPC zones for a floor plan."""

    def create_wall(self, data: dict):
        """Create a wall persistence entity."""

    def create_door(self, data: dict):
        """Create a door persistence entity."""

    def create_window(self, data: dict):
        """Create a window persistence entity."""

    def create_stair(self, data: dict):
        """Create a stair persistence entity."""

    def create_room(self, data: dict):
        """Create a room persistence entity."""

    def create_dimension(self, data: dict):
        """Create a dimension persistence entity."""

    def create_fire_alarm(self, data: dict):
        """Create a fire alarm persistence entity."""

    def get_optional_by_type(self, element_type: str, entity_id: int):
        """Return an optional persistence entity for the requested element type."""

    def add(self, entity) -> None:
        """Track an entity for persistence."""

    def delete(self, entity) -> None:
        """Delete an entity from persistence."""

    def flush(self) -> None:
        """Flush staged changes."""

    def refresh(self, entity) -> None:
        """Refresh an entity from persistence."""

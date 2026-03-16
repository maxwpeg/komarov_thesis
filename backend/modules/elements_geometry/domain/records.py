"""Domain records for element geometry aggregates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PayloadRecord:
    """Small mapper record decoupled from ORM models."""

    payload: dict[str, Any]

    @classmethod
    def from_model(cls, model) -> "PayloadRecord":
        return cls(deepcopy(model.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)


class WallRecord(PayloadRecord):
    """Wall read model."""


class DoorRecord(PayloadRecord):
    """Door read model."""


class WindowRecord(PayloadRecord):
    """Window read model."""


class StairRecord(PayloadRecord):
    """Stair read model."""


class RoomRecord(PayloadRecord):
    """Room read model."""


class DimensionRecord(PayloadRecord):
    """Dimension read model."""


class FireAlarmRecord(PayloadRecord):
    """Fire alarm read model."""

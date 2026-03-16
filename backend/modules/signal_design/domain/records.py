"""Domain records for signal design aggregates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PayloadRecord:
    """Simple ORM-independent payload wrapper."""

    payload: dict[str, Any]

    @classmethod
    def from_model(cls, model) -> "PayloadRecord":
        return cls(deepcopy(model.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)


class ZkspcZoneRecord(PayloadRecord):
    """ZKSPC zone read model."""


class SignalInstrumentRecord(PayloadRecord):
    """Signal instrument read model."""


class CableRouteRecord(PayloadRecord):
    """Cable route read model."""

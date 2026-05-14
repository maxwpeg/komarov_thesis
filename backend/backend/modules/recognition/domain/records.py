"""Domain records for recognition workflows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RecognitionRecord:
    """Recognition result record detached from ORM."""

    payload: dict[str, Any]

    @classmethod
    def from_model(cls, model) -> "RecognitionRecord":
        return cls(deepcopy(model.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)

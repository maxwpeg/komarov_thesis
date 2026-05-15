"""Application errors for the pipeline module."""

from __future__ import annotations


class WallValidationError(Exception):
    """Raised when wall commit is blocked by missing wall dimensions."""

    def __init__(self, missing_wall_ids: list[int]):
        self.missing_wall_ids = missing_wall_ids
        super().__init__(f"Missing dimensions for walls: {missing_wall_ids}")


"""Infrastructure adapter for the external floorplan recognizer."""

from __future__ import annotations

from backend.floorplan_integration import FloorplanRecognitionIntegrator


class FloorplanRecognitionAdapter:
    """Thin adapter over the external recognizer integration."""

    def __init__(self, *, debug: bool):
        self.integrator = FloorplanRecognitionIntegrator(debug=debug)

    def recognize(self, image_path: str, *, floor_plan_id: int, debug_dir: str | None):
        return self.integrator.recognize_floor_plan(
            image_path,
            floor_plan_id=floor_plan_id,
            debug_dir=debug_dir,
        )

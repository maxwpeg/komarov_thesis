"""Compatibility adapter around the legacy pipeline service."""

from __future__ import annotations

from backend.modules.pipeline.ports.orchestrator import PipelineOrchestrator
from backend.services.pipeline_service import PipelineService


class LegacyPipelineOrchestrator(PipelineOrchestrator):
    """Delegate pipeline orchestration to the current compatibility service."""

    def __init__(self, service: PipelineService):
        self._service = service

    def get_pipeline_state(self, floor_plan_id: int):
        return self._service.get_pipeline_state(floor_plan_id)

    def detect_walls(self, floor_plan_id: int):
        return self._service.detect_walls(floor_plan_id)

    def commit_walls(self, floor_plan_id: int, payload):
        return self._service.commit_walls(floor_plan_id, payload)

    def detect_openings(self, floor_plan_id: int):
        return self._service.detect_openings(floor_plan_id)

    def commit_openings(self, floor_plan_id: int, payload):
        return self._service.commit_openings(floor_plan_id, payload)

    def detect_rooms(self, floor_plan_id: int):
        return self._service.detect_rooms(floor_plan_id)

    def commit_rooms(self, floor_plan_id: int, payload):
        return self._service.commit_rooms(floor_plan_id, payload)

    def detect_zkspc(self, floor_plan_id: int):
        return self._service.detect_zkspc(floor_plan_id)

    def commit_zkspc(self, floor_plan_id: int, payload):
        return self._service.commit_zkspc(floor_plan_id, payload)


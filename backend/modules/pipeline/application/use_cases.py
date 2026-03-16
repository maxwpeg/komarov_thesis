"""Explicit application-facing pipeline orchestration use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.modules.pipeline.ports.orchestrator import PipelineOrchestrator
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher


@dataclass(slots=True)
class PipelineQueryUseCases:
    """Read-only pipeline queries."""

    service: PipelineOrchestrator

    def get_pipeline_state(self, floor_plan_id: int):
        return self.service.get_pipeline_state(floor_plan_id)


@dataclass(slots=True)
class WallsStepUseCases:
    """Pipeline handlers for the walls step."""

    service: PipelineOrchestrator
    events: Any

    def detect(self, floor_plan_id: int):
        floor_plan, state = self.service.detect_walls(floor_plan_id)
        self.events.publish(
            "pipeline_walls_detected",
            {"category": "pipeline", "use_case": "DetectWalls", "floor_plan_id": floor_plan_id, "pipeline_step": "walls"},
        )
        return floor_plan, state

    def commit(self, floor_plan_id: int, payload):
        floor_plan, state = self.service.commit_walls(floor_plan_id, payload)
        self.events.publish(
            "pipeline_walls_committed",
            {"category": "pipeline", "use_case": "CommitWalls", "floor_plan_id": floor_plan_id, "pipeline_step": "walls"},
        )
        return floor_plan, state


@dataclass(slots=True)
class OpeningsStepUseCases:
    """Pipeline handlers for the openings step."""

    service: PipelineOrchestrator
    events: Any

    def detect(self, floor_plan_id: int):
        floor_plan, state = self.service.detect_openings(floor_plan_id)
        self.events.publish(
            "pipeline_openings_detected",
            {"category": "pipeline", "use_case": "DetectOpenings", "floor_plan_id": floor_plan_id, "pipeline_step": "openings"},
        )
        return floor_plan, state

    def commit(self, floor_plan_id: int, payload):
        floor_plan, state = self.service.commit_openings(floor_plan_id, payload)
        self.events.publish(
            "pipeline_openings_committed",
            {"category": "pipeline", "use_case": "CommitOpenings", "floor_plan_id": floor_plan_id, "pipeline_step": "openings"},
        )
        return floor_plan, state


@dataclass(slots=True)
class RoomsStepUseCases:
    """Pipeline handlers for the rooms step."""

    service: PipelineOrchestrator
    events: Any

    def detect(self, floor_plan_id: int):
        floor_plan, state = self.service.detect_rooms(floor_plan_id)
        self.events.publish(
            "pipeline_rooms_detected",
            {"category": "pipeline", "use_case": "DetectRooms", "floor_plan_id": floor_plan_id, "pipeline_step": "rooms"},
        )
        return floor_plan, state

    def commit(self, floor_plan_id: int, payload):
        floor_plan, state = self.service.commit_rooms(floor_plan_id, payload)
        self.events.publish(
            "pipeline_rooms_committed",
            {"category": "pipeline", "use_case": "CommitRooms", "floor_plan_id": floor_plan_id, "pipeline_step": "rooms"},
        )
        return floor_plan, state


@dataclass(slots=True)
class ZkspcStepUseCases:
    """Pipeline handlers for the ZKSPC step."""

    service: PipelineOrchestrator
    events: Any

    def detect(self, floor_plan_id: int):
        floor_plan, state = self.service.detect_zkspc(floor_plan_id)
        self.events.publish(
            "pipeline_zkspc_detected",
            {"category": "pipeline", "use_case": "DetectZkspc", "floor_plan_id": floor_plan_id, "pipeline_step": "zkspc"},
        )
        return floor_plan, state

    def commit(self, floor_plan_id: int, payload):
        floor_plan, state = self.service.commit_zkspc(floor_plan_id, payload)
        self.events.publish(
            "pipeline_zkspc_committed",
            {"category": "pipeline", "use_case": "CommitZkspc", "floor_plan_id": floor_plan_id, "pipeline_step": "zkspc"},
        )
        return floor_plan, state


class PipelineUseCases:
    """Composition root for explicit pipeline handlers."""

    def __init__(self, service: PipelineOrchestrator, events: Any | None = None):
        publisher = events or NoOpEventPublisher()
        self.query = PipelineQueryUseCases(service)
        self.walls = WallsStepUseCases(service, publisher)
        self.openings = OpeningsStepUseCases(service, publisher)
        self.rooms = RoomsStepUseCases(service, publisher)
        self.zkspc = ZkspcStepUseCases(service, publisher)

    def get_pipeline_state(self, floor_plan_id: int):
        return self.query.get_pipeline_state(floor_plan_id)

    def detect_walls(self, floor_plan_id: int):
        return self.walls.detect(floor_plan_id)

    def commit_walls(self, floor_plan_id: int, payload):
        return self.walls.commit(floor_plan_id, payload)

    def detect_openings(self, floor_plan_id: int):
        return self.openings.detect(floor_plan_id)

    def commit_openings(self, floor_plan_id: int, payload):
        return self.openings.commit(floor_plan_id, payload)

    def detect_rooms(self, floor_plan_id: int):
        return self.rooms.detect(floor_plan_id)

    def commit_rooms(self, floor_plan_id: int, payload):
        return self.rooms.commit(floor_plan_id, payload)

    def detect_zkspc(self, floor_plan_id: int):
        return self.zkspc.detect(floor_plan_id)

    def commit_zkspc(self, floor_plan_id: int, payload):
        return self.zkspc.commit(floor_plan_id, payload)

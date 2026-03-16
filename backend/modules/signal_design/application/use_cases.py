"""Explicit application use cases for signal design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.errors import AppError
from backend.modules.elements_geometry.domain.policies import FireAlarmMetadataPolicy
from backend.modules.pipeline.application.branch_state import update_signal_branch_state
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher
from backend.modules.signal_design.domain.policies import CableRoutingPolicy, FireAlarmLayoutPolicy, ZkspcPlanningPolicy
from backend.modules.signal_design.domain.records import CableRouteRecord, SignalInstrumentRecord, ZkspcZoneRecord
from backend.modules.signal_design.ports.repositories import SignalDesignRepository
from backend.schemas import ZkspcZoneCommit
from backend.signal_planning import MERGE_CAPABLE_INSTRUMENTS


def _default_zone_warnings(room_count: int, area_sqm: float) -> list[str]:
    warnings = [
        "Пожарные отсеки, номера и расстояния между изолированными выходами требуют ручной проверки.",
    ]
    if room_count > 5:
        warnings.append("В ЗКСПС более 5 помещений.")
    if area_sqm > 2000.0:
        warnings.append("Площадь ЗКСПС превышает 2000 м2.")
    return warnings


@dataclass(slots=True)
class ZkspcUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def list_zkspc_zones(self, floor_plan_id: int) -> list[ZkspcZoneRecord]:
        return [ZkspcZoneRecord.from_model(zone) for zone in self.repository.list_zones(floor_plan_id)]

    def detect_zkspc(self, floor_plan_id: int) -> list[ZkspcZoneRecord]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        zones = ZkspcPlanningPolicy.detect([room.to_dict() for room in floor_plan.rooms])
        return self.replace_zkspc_zones(
            floor_plan_id,
            [ZkspcZoneCommit.model_validate({**zone, "id": None}) for zone in zones],
        )

    def replace_zkspc_zones(self, floor_plan_id: int, zones: list[ZkspcZoneCommit]) -> list[ZkspcZoneRecord]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        room_map = {room.id: room for room in floor_plan.rooms}
        self.repository.delete_zones_for_floor_plan(floor_plan_id)
        self.repository.flush()

        for index, zone_payload in enumerate(zones, start=1):
            room_ids = [int(room_id) for room_id in zone_payload.room_ids if int(room_id) in room_map]
            rooms = [room_map[room_id] for room_id in room_ids]
            area_sqm = round(sum(float(room.area_sqm or 0.0) for room in rooms), 2)
            zone = self.repository.create_zone(
                {
                    "floor_plan_id": floor_plan_id,
                    "zone_number": zone_payload.zone_number or index,
                    "name": (zone_payload.name or f"ЗКСПС {zone_payload.zone_number or index}").strip(),
                    "area_sqm": area_sqm,
                    "room_count": len(room_ids),
                    "is_manual": zone_payload.is_manual,
                    "is_locked": zone_payload.is_locked,
                    "compliance_warnings": _default_zone_warnings(len(room_ids), area_sqm),
                }
            )
            self.repository.add(zone)
            self.repository.flush()
            for room_id in room_ids:
                self.repository.add(self.repository.create_zone_room(zone.id, room_id))

        self.repository.flush()
        self._refresh_fire_alarm_zone_assignments(floor_plan_id)
        self.uow.commit()
        self.events.publish(
            "zkspc_saved",
            {"category": "signal_design", "use_case": "ReplaceZkspcZones", "floor_plan_id": floor_plan_id},
        )
        return [ZkspcZoneRecord.from_model(zone) for zone in self.repository.list_zones(floor_plan_id)]

    def _refresh_fire_alarm_zone_assignments(self, floor_plan_id: int) -> None:
        zones = self.repository.list_zones(floor_plan_id)
        room_to_zone: dict[int, Any] = {}
        for zone in zones:
            for room_id in [link.room_id for link in zone.room_links]:
                room_to_zone[int(room_id)] = zone
        for alarm in self.repository.list_fire_alarms(floor_plan_id):
            zone = room_to_zone.get(int(alarm.room_id)) if alarm.room_id is not None and int(alarm.room_id) in room_to_zone else None
            alarm.zkspc_zone_id = zone.id if zone is not None else None
            alarm.zone = str(zone.zone_number) if zone is not None else None


@dataclass(slots=True)
class FireAlarmLayoutUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def auto_layout_fire_alarms(self, floor_plan_id: int, system_type: str) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        return FireAlarmLayoutPolicy.preview(
            floor_plan.to_dict(include_elements=True),
            scale_factor=floor_plan.scale_factor,
            system_type=system_type,
            zkspc_zones=[zone.to_dict() for zone in self.repository.list_zones(floor_plan_id)],
        )

    def replace_branch_fire_alarms(self, floor_plan_id: int, system_type: str, payloads: list[dict[str, Any]]) -> None:
        normalized_system = self._normalize_system_type(system_type)
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        self.repository.delete_fire_alarms_for_branch(floor_plan_id, normalized_system)
        for payload in payloads:
            normalized = self._normalize_fire_alarm_payload(
                floor_plan_id,
                {
                    "floor_plan_id": floor_plan_id,
                    "system_type": normalized_system,
                    **payload,
                },
            )
            self.repository.add(self.repository.create_fire_alarm(normalized))
        update_signal_branch_state(
            floor_plan,
            normalized_system,
            fire_alarms_status="validated",
            devices_cables_status="draft",
            active_step="devices_cables",
        )
        self.uow.commit()
        self.events.publish(
            "branch_fire_alarms_saved",
            {"category": "signal_design", "use_case": "ReplaceBranchFireAlarms", "floor_plan_id": floor_plan_id, "system_type": normalized_system},
        )

    def _normalize_fire_alarm_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in floor_plan.rooms]
        return FireAlarmMetadataPolicy.normalize(
            floor_plan_id=floor_plan_id,
            data=data,
            scale_factor=floor_plan.scale_factor or 1.0,
            rooms=rooms,
            zone_lookup=lambda room_id: self._find_zone_for_room(floor_plan_id, room_id),
        )

    def _find_zone_for_room(self, floor_plan_id: int, room_id: int):
        for zone in self.repository.list_zones(floor_plan_id):
            if any(link.room_id == room_id for link in zone.room_links):
                return zone
        return None

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {"addressable", "non_addressable"} else "non_addressable"


@dataclass(slots=True)
class SignalInstrumentUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def list_signal_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentRecord]:
        normalized_system = self._normalize_system_type(system_type) if system_type else None
        return [SignalInstrumentRecord.from_model(item) for item in self.repository.list_instruments(floor_plan_id, normalized_system)]

    def create_signal_instrument(self, payload) -> SignalInstrumentRecord:
        system_type = self._normalize_system_type(payload.system_type)
        floor_plan = self.repository.get_floor_plan(payload.floor_plan_id)
        existing = self.repository.list_instruments(payload.floor_plan_id, system_type)
        if existing:
            raise AppError(409, "instrument_limit_reached", "Only one primary instrument per system is supported")
        instrument = self.repository.create_instrument(
            {
                "floor_plan_id": payload.floor_plan_id,
                "system_type": system_type,
                "instrument_type": payload.instrument_type,
                "x": float(payload.x),
                "y": float(payload.y),
                "name": payload.name or self._default_instrument_name(payload.instrument_type, system_type),
                "supports_cable_merge": (
                    payload.supports_cable_merge
                    if payload.supports_cable_merge is not None
                    else payload.instrument_type in MERGE_CAPABLE_INSTRUMENTS
                ),
            }
        )
        self.repository.add(instrument)
        self.repository.flush()
        CableRoutingUseCases(self.repository, self.uow, self.events)._replace_routes_for_instrument(instrument, use_shared_trunk=False)
        update_signal_branch_state(
            floor_plan,
            system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.uow.commit()
        self.repository.refresh(instrument)
        return SignalInstrumentRecord.from_model(instrument)

    def update_signal_instrument(self, instrument_id: int, payload) -> SignalInstrumentRecord:
        instrument = self.repository.get_instrument(instrument_id)
        if payload.floor_plan_id is not None:
            instrument.floor_plan_id = payload.floor_plan_id
        if payload.system_type is not None:
            instrument.system_type = self._normalize_system_type(payload.system_type)
        if payload.instrument_type is not None:
            instrument.instrument_type = payload.instrument_type
            if payload.supports_cable_merge is None:
                instrument.supports_cable_merge = payload.instrument_type in MERGE_CAPABLE_INSTRUMENTS
        if payload.x is not None:
            instrument.x = float(payload.x)
        if payload.y is not None:
            instrument.y = float(payload.y)
        if payload.name is not None:
            instrument.name = payload.name
        if payload.supports_cable_merge is not None:
            instrument.supports_cable_merge = payload.supports_cable_merge
        self.repository.flush()
        CableRoutingUseCases(self.repository, self.uow, self.events)._replace_routes_for_instrument(instrument, use_shared_trunk=False)
        update_signal_branch_state(
            self.repository.get_floor_plan(instrument.floor_plan_id),
            instrument.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.uow.commit()
        self.repository.refresh(instrument)
        return SignalInstrumentRecord.from_model(instrument)

    def delete_signal_instrument(self, instrument_id: int) -> None:
        instrument = self.repository.get_instrument(instrument_id)
        floor_plan = self.repository.get_floor_plan(instrument.floor_plan_id)
        system_type = instrument.system_type
        self.repository.delete(instrument)
        update_signal_branch_state(
            floor_plan,
            system_type,
            devices_cables_status="draft",
            active_step="fire_alarms",
        )
        self.uow.commit()

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {"addressable", "non_addressable"} else "non_addressable"

    @staticmethod
    def _default_instrument_name(instrument_type: str, system_type: str) -> str:
        prefix = "Адресный" if system_type == "addressable" else "Безадресный"
        labels = {
            "control_panel": "контрольный прибор",
            "loop_controller": "контроллер шлейфа",
            "annunciator": "оповещатель",
        }
        return f"{prefix} {labels.get(instrument_type, 'прибор')}"


@dataclass(slots=True)
class CableRoutingUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def list_cable_routes(self, floor_plan_id: int, system_type: str | None = None) -> list[CableRouteRecord]:
        normalized_system = self._normalize_system_type(system_type) if system_type else None
        return [CableRouteRecord.from_model(route) for route in self.repository.list_routes(floor_plan_id, normalized_system)]

    def recalculate_routes(self, floor_plan_id: int, system_type: str, use_shared_trunk: bool = False) -> list[CableRouteRecord]:
        instrument = self._require_single_instrument(floor_plan_id, system_type)
        self._replace_routes_for_instrument(instrument, use_shared_trunk=use_shared_trunk)
        update_signal_branch_state(
            self.repository.get_floor_plan(floor_plan_id),
            instrument.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.uow.commit()
        self.events.publish(
            "cable_routes_recalculated",
            {"category": "signal_design", "use_case": "RecalculateCableRoutes", "floor_plan_id": floor_plan_id, "system_type": instrument.system_type},
        )
        return [CableRouteRecord.from_model(route) for route in self.repository.list_routes(floor_plan_id, system_type)]

    def update_cable_route(self, route_id: int, payload) -> CableRouteRecord:
        route = self.repository.get_route(route_id)
        route.polyline_points = payload.polyline_points
        route.is_manual = payload.is_manual
        floor_plan = self.repository.get_floor_plan(route.floor_plan_id)
        route.length_m = CableRoutingPolicy.length(route.polyline_points or [], floor_plan.scale_factor)
        update_signal_branch_state(
            floor_plan,
            route.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.uow.commit()
        self.repository.refresh(route)
        return CableRouteRecord.from_model(route)

    def _replace_routes_for_instrument(self, instrument, *, use_shared_trunk: bool) -> None:
        floor_plan = self.repository.get_floor_plan(instrument.floor_plan_id)
        alarms = [alarm.to_dict() for alarm in self.repository.list_fire_alarms(instrument.floor_plan_id, instrument.system_type)]
        routes = CableRoutingPolicy.recalculate(
            floor_plan.to_dict(include_elements=True),
            system_type=instrument.system_type,
            instrument=instrument.to_dict(),
            alarms=alarms,
            use_shared_trunk=use_shared_trunk and instrument.supports_cable_merge,
        )
        self.repository.delete_routes_for_instrument(instrument.id)
        for route_payload in routes:
            self.repository.add(
                self.repository.create_route(
                    {
                        "floor_plan_id": instrument.floor_plan_id,
                        **route_payload,
                    }
                )
            )
        self.repository.flush()

    def _require_single_instrument(self, floor_plan_id: int, system_type: str):
        normalized_system = self._normalize_system_type(system_type)
        instruments = self.repository.list_instruments(floor_plan_id, normalized_system)
        if not instruments:
            raise AppError(404, "instrument_not_found", "Signal instrument not found")
        return instruments[0]

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {"addressable", "non_addressable"} else "non_addressable"


class SignalDesignUseCases:
    """Composition root for signal design use cases."""

    def __init__(self, repository: SignalDesignRepository, uow: UnitOfWork, events: Any | None = None):
        publisher = events or NoOpEventPublisher()
        self.zkspc = ZkspcUseCases(repository, uow, publisher)
        self.fire_alarm_layout = FireAlarmLayoutUseCases(repository, uow, publisher)
        self.instruments = SignalInstrumentUseCases(repository, uow, publisher)
        self.cable_routing = CableRoutingUseCases(repository, uow, publisher)

    def list_zkspc_zones(self, floor_plan_id: int) -> list[ZkspcZoneRecord]:
        return self.zkspc.list_zkspc_zones(floor_plan_id)

    def detect_zkspc(self, floor_plan_id: int) -> list[ZkspcZoneRecord]:
        return self.zkspc.detect_zkspc(floor_plan_id)

    def replace_zkspc_zones(self, floor_plan_id: int, zones: list[ZkspcZoneCommit]) -> list[ZkspcZoneRecord]:
        return self.zkspc.replace_zkspc_zones(floor_plan_id, zones)

    def auto_layout_fire_alarms(self, floor_plan_id: int, system_type: str) -> dict[str, Any]:
        return self.fire_alarm_layout.auto_layout_fire_alarms(floor_plan_id, system_type)

    def replace_branch_fire_alarms(self, floor_plan_id: int, system_type: str, payloads: list[dict[str, Any]]) -> None:
        self.fire_alarm_layout.replace_branch_fire_alarms(floor_plan_id, system_type, payloads)

    def list_signal_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentRecord]:
        return self.instruments.list_signal_instruments(floor_plan_id, system_type)

    def create_signal_instrument(self, payload) -> SignalInstrumentRecord:
        return self.instruments.create_signal_instrument(payload)

    def update_signal_instrument(self, instrument_id: int, payload) -> SignalInstrumentRecord:
        return self.instruments.update_signal_instrument(instrument_id, payload)

    def delete_signal_instrument(self, instrument_id: int) -> None:
        self.instruments.delete_signal_instrument(instrument_id)

    def list_cable_routes(self, floor_plan_id: int, system_type: str | None = None) -> list[CableRouteRecord]:
        return self.cable_routing.list_cable_routes(floor_plan_id, system_type)

    def recalculate_routes(self, floor_plan_id: int, system_type: str, use_shared_trunk: bool = False) -> list[CableRouteRecord]:
        return self.cable_routing.recalculate_routes(floor_plan_id, system_type, use_shared_trunk)

    def update_cable_route(self, route_id: int, payload) -> CableRouteRecord:
        return self.cable_routing.update_cable_route(route_id, payload)

"""Explicit application use cases for signal design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.errors import AppError
from backend.modules.equipment.domain.bindings import (
    ensure_model_equipment_assignments,
    list_project_equipment_items,
    resolve_project_equipment_id,
)
from backend.modules.equipment.domain.constants import (
    FIRE_ALARM_DEVICE_CATEGORY_MAP,
    SIGNAL_INSTRUMENT_CATEGORY_MAP,
    SOUE_DEVICE_CATEGORY_MAP,
)
from backend.modules.elements_geometry.domain.policies import FireAlarmMetadataPolicy, SoueDeviceMetadataPolicy
from backend.modules.pipeline.application.branch_state import update_signal_branch_state
from backend.modules.pipeline.domain.state import COMMON_SIGNAL_BRANCH, SPS_SIGNAL_BRANCHES
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher
from backend.modules.signal_design.domain.policies import CableRoutingPolicy, FireAlarmLayoutPolicy, SoueLayoutPolicy, ZkspcPlanningPolicy
from backend.modules.signal_design.domain.records import CableRouteRecord, SignalInstrumentRecord, SoueDeviceRecord, ZkspcZoneRecord
from backend.modules.signal_design.ports.repositories import SignalDesignRepository
from backend.schemas import ZkspcZoneCommit
from backend.signal_planning import (
    MERGE_CAPABLE_INSTRUMENTS,
    ROUTE_KIND_ORDER,
    SPS_SUBSYSTEM,
    SOUE_SUBSYSTEM,
    build_device_route_metadata,
    normalize_branch_route_numbers,
    should_show_zc_terminator,
)


def _default_zone_warnings(room_count: int, area_sqm: float) -> list[str]:
    warnings = [
        "Пожарные отсеки, номера и расстояния между изолированными выходами требуют ручной проверки.",
    ]
    if room_count > 5:
        warnings.append("В ЗКСПС более 5 помещений.")
    if area_sqm > 2000.0:
        warnings.append("Площадь ЗКСПС превышает 2000 м2.")
    return warnings


def _normalize_sps_system_type(value: str | None) -> str:
    return value if value in SPS_SIGNAL_BRANCHES else "non_addressable"


def _normalize_common_signal_type(_value: str | None = None) -> str:
    return COMMON_SIGNAL_BRANCH


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
        layout = FireAlarmLayoutPolicy.preview(
            floor_plan.to_dict(include_elements=True),
            scale_factor=floor_plan.scale_factor,
            system_type=system_type,
            zkspc_zones=[zone.to_dict() for zone in self.repository.list_zones(floor_plan_id)],
        )
        for device in layout.get("all_devices", []):
            device["equipment_id"] = resolve_project_equipment_id(
                floor_plan,
                FIRE_ALARM_DEVICE_CATEGORY_MAP.get(str(device.get("device_type") or ""), ()),
                device.get("equipment_id"),
                entity_label="fire alarm device",
                require_on_ambiguous=False,
            )
        return layout

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
        self.repository.flush()
        self.repository.delete_routes_for_branch(floor_plan_id, normalized_system, subsystem_type=SPS_SUBSYSTEM)
        CableRoutingUseCases(self.repository, self.uow, self.events)._sync_branch_routes_and_metadata(
            floor_plan_id,
            normalized_system,
            floor_plan=floor_plan,
            subsystem_type=SPS_SUBSYSTEM,
            fire_alarms_status="validated",
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
        ) | {
            "equipment_id": resolve_project_equipment_id(
                floor_plan,
                FIRE_ALARM_DEVICE_CATEGORY_MAP.get(str(data.get("device_type") or ""), ()),
                data.get("equipment_id"),
                entity_label="fire alarm device",
            )
        }

    def _find_zone_for_room(self, floor_plan_id: int, room_id: int):
        for zone in self.repository.list_zones(floor_plan_id):
            if any(link.room_id == room_id for link in zone.room_links):
                return zone
        return None

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {"addressable", "non_addressable"} else "non_addressable"


@dataclass(slots=True)
class SoueLayoutUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def _migrate_legacy_common_branch_data(self, floor_plan_id: int) -> None:
        common_devices = self.repository.list_soue_devices(floor_plan_id, COMMON_SIGNAL_BRANCH)
        common_routes = self.repository.list_routes(floor_plan_id, COMMON_SIGNAL_BRANCH, SOUE_SUBSYSTEM)
        if common_devices or common_routes:
            return
        legacy_devices = self.repository.list_soue_devices(floor_plan_id, "non_addressable")
        legacy_routes = self.repository.list_routes(floor_plan_id, "non_addressable", SOUE_SUBSYSTEM)
        if not legacy_devices and not legacy_routes:
            return
        for device in legacy_devices:
            device.system_type = COMMON_SIGNAL_BRANCH
        for route in legacy_routes:
            route.system_type = COMMON_SIGNAL_BRANCH
        self.repository.flush()

    def list_soue_devices(self, floor_plan_id: int, system_type: str | None = None) -> list[SoueDeviceRecord]:
        self._migrate_legacy_common_branch_data(floor_plan_id)
        normalized_system = self._normalize_system_type(system_type) if system_type else COMMON_SIGNAL_BRANCH
        return [SoueDeviceRecord.from_model(item) for item in self.repository.list_soue_devices(floor_plan_id, normalized_system)]

    def auto_layout_soue_devices(self, floor_plan_id: int, system_type: str) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        layout = SoueLayoutPolicy.preview(
            floor_plan.to_dict(include_elements=True),
            scale_factor=floor_plan.scale_factor,
            system_type=system_type,
        )
        for device in layout.get("devices", []):
            device["equipment_id"] = resolve_project_equipment_id(
                floor_plan,
                SOUE_DEVICE_CATEGORY_MAP.get(str(device.get("device_type") or ""), ()),
                device.get("equipment_id"),
                entity_label="SOUE device",
                require_on_ambiguous=False,
            )
        return layout

    def replace_branch_soue_devices(self, floor_plan_id: int, system_type: str, payloads: list[dict[str, Any]]) -> None:
        normalized_system = self._normalize_system_type(system_type)
        self._migrate_legacy_common_branch_data(floor_plan_id)
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        for device in list(self.repository.list_soue_devices(floor_plan_id, normalized_system)):
            self.repository.delete(device)
        for payload in payloads:
            normalized = self._normalize_soue_device_payload(
                floor_plan_id,
                {
                    "floor_plan_id": floor_plan_id,
                    "system_type": normalized_system,
                    **payload,
                },
            )
            self.repository.add(self.repository.create_soue_device(normalized))
        self.repository.flush()
        self.repository.delete_routes_for_branch(floor_plan_id, normalized_system, subsystem_type=SOUE_SUBSYSTEM)
        CableRoutingUseCases(self.repository, self.uow, self.events)._sync_branch_routes_and_metadata(
            floor_plan_id,
            normalized_system,
            floor_plan=floor_plan,
            subsystem_type=SOUE_SUBSYSTEM,
            soue_devices_status="validated",
        )
        self.uow.commit()
        self.events.publish(
            "branch_soue_devices_saved",
            {"category": "signal_design", "use_case": "ReplaceBranchSoueDevices", "floor_plan_id": floor_plan_id, "system_type": normalized_system},
        )

    def _normalize_soue_device_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in floor_plan.rooms]
        return SoueDeviceMetadataPolicy.normalize(
            floor_plan_id=floor_plan_id,
            data=data,
            scale_factor=floor_plan.scale_factor or 1.0,
            rooms=rooms,
        ) | {
            "equipment_id": resolve_project_equipment_id(
                floor_plan,
                SOUE_DEVICE_CATEGORY_MAP.get(str(data.get("device_type") or ""), ()),
                data.get("equipment_id"),
                entity_label="SOUE device",
            )
        }

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return _normalize_common_signal_type(value)


@dataclass(slots=True)
class SignalInstrumentUseCases:
    repository: SignalDesignRepository
    uow: UnitOfWork
    events: Any

    def _migrate_legacy_common_branch_data(self, floor_plan_id: int) -> None:
        common_instruments = self.repository.list_instruments(floor_plan_id, COMMON_SIGNAL_BRANCH)
        if common_instruments:
            return
        legacy_instruments = self.repository.list_instruments(floor_plan_id, "non_addressable")
        if not legacy_instruments:
            return
        for instrument in legacy_instruments:
            instrument.system_type = COMMON_SIGNAL_BRANCH
        self.repository.flush()

    def list_signal_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentRecord]:
        self._migrate_legacy_common_branch_data(floor_plan_id)
        normalized_system = self._normalize_system_type(system_type) if system_type else COMMON_SIGNAL_BRANCH
        return [SignalInstrumentRecord.from_model(item) for item in self.repository.list_instruments(floor_plan_id, normalized_system)]

    def create_signal_instrument(self, payload) -> SignalInstrumentRecord:
        system_type = self._normalize_system_type(payload.system_type)
        floor_plan = self.repository.get_floor_plan(payload.floor_plan_id)
        self._migrate_legacy_common_branch_data(payload.floor_plan_id)
        equipment_id = resolve_project_equipment_id(
            floor_plan,
            SIGNAL_INSTRUMENT_CATEGORY_MAP.get(str(payload.instrument_type or ""), ()),
            payload.equipment_id,
            entity_label="signal instrument",
        )
        project_equipment_by_id = {
            int(getattr(item, "id")): item
            for item in list_project_equipment_items(floor_plan)
            if getattr(item, "id", None) is not None
        }
        equipment_name = (
            str(getattr(project_equipment_by_id[int(equipment_id)], "name", "") or "").strip()
            if equipment_id is not None and int(equipment_id) in project_equipment_by_id
            else None
        )
        instrument = self.repository.create_instrument(
            {
                "floor_plan_id": payload.floor_plan_id,
                "system_type": system_type,
                "instrument_type": payload.instrument_type,
                "equipment_id": equipment_id,
                "x": float(payload.x),
                "y": float(payload.y),
                "name": payload.name or equipment_name or self._default_instrument_name(payload.instrument_type, system_type),
                "supports_cable_merge": (
                    payload.supports_cable_merge
                    if payload.supports_cable_merge is not None
                    else payload.instrument_type in MERGE_CAPABLE_INSTRUMENTS
                ),
                "label_dx": payload.label_dx,
                "label_dy": payload.label_dy,
            }
        )
        self.repository.add(instrument)
        self.repository.flush()
        cable_routing = CableRoutingUseCases(self.repository, self.uow, self.events)
        for sps_system in SPS_SIGNAL_BRANCHES:
            if self.repository.list_fire_alarms(payload.floor_plan_id, sps_system) or self.repository.list_routes(
                payload.floor_plan_id,
                sps_system,
                SPS_SUBSYSTEM,
            ):
                cable_routing._sync_branch_routes_and_metadata(
                    payload.floor_plan_id,
                    sps_system,
                    floor_plan=floor_plan,
                    subsystem_type=SPS_SUBSYSTEM,
                )
        if self.repository.list_soue_devices(payload.floor_plan_id, COMMON_SIGNAL_BRANCH) or self.repository.list_routes(
            payload.floor_plan_id,
            COMMON_SIGNAL_BRANCH,
            SOUE_SUBSYSTEM,
        ):
            cable_routing._sync_branch_routes_and_metadata(
                payload.floor_plan_id,
                COMMON_SIGNAL_BRANCH,
                floor_plan=floor_plan,
                subsystem_type=SOUE_SUBSYSTEM,
            )
        update_signal_branch_state(
            floor_plan,
            system_type,
            signal_instruments_status="draft",
            active_step="signal_instruments",
        )
        self.uow.commit()
        self.repository.refresh(instrument)
        return SignalInstrumentRecord.from_model(instrument)

    def update_signal_instrument(self, instrument_id: int, payload) -> SignalInstrumentRecord:
        instrument = self.repository.get_instrument(instrument_id)
        self._migrate_legacy_common_branch_data(instrument.floor_plan_id)
        target_floor_plan_id = payload.floor_plan_id if payload.floor_plan_id is not None else instrument.floor_plan_id
        target_floor_plan = self.repository.get_floor_plan(target_floor_plan_id)
        target_instrument_type = payload.instrument_type if payload.instrument_type is not None else instrument.instrument_type
        target_equipment_id = resolve_project_equipment_id(
            target_floor_plan,
            SIGNAL_INSTRUMENT_CATEGORY_MAP.get(str(target_instrument_type or ""), ()),
            payload.equipment_id if "equipment_id" in payload.model_fields_set else instrument.equipment_id,
            entity_label="signal instrument",
        )
        if payload.floor_plan_id is not None:
            instrument.floor_plan_id = payload.floor_plan_id
        if payload.system_type is not None:
            instrument.system_type = self._normalize_system_type(payload.system_type)
        if payload.instrument_type is not None:
            instrument.instrument_type = payload.instrument_type
            if payload.supports_cable_merge is None:
                instrument.supports_cable_merge = payload.instrument_type in MERGE_CAPABLE_INSTRUMENTS
        instrument.equipment_id = target_equipment_id
        if payload.x is not None:
            instrument.x = float(payload.x)
        if payload.y is not None:
            instrument.y = float(payload.y)
        if payload.name is not None:
            instrument.name = payload.name
        if payload.supports_cable_merge is not None:
            instrument.supports_cable_merge = payload.supports_cable_merge
        if payload.label_dx is not None:
            instrument.label_dx = float(payload.label_dx)
        if payload.label_dy is not None:
            instrument.label_dy = float(payload.label_dy)
        self.repository.flush()
        cable_routing = CableRoutingUseCases(self.repository, self.uow, self.events)
        for sps_system in SPS_SIGNAL_BRANCHES:
            if self.repository.list_fire_alarms(instrument.floor_plan_id, sps_system) or self.repository.list_routes(
                instrument.floor_plan_id,
                sps_system,
                SPS_SUBSYSTEM,
            ):
                cable_routing._sync_branch_routes_and_metadata(
                    instrument.floor_plan_id,
                    sps_system,
                    subsystem_type=SPS_SUBSYSTEM,
                )
        if self.repository.list_soue_devices(instrument.floor_plan_id, COMMON_SIGNAL_BRANCH) or self.repository.list_routes(
            instrument.floor_plan_id,
            COMMON_SIGNAL_BRANCH,
            SOUE_SUBSYSTEM,
        ):
            cable_routing._sync_branch_routes_and_metadata(
                instrument.floor_plan_id,
                COMMON_SIGNAL_BRANCH,
                subsystem_type=SOUE_SUBSYSTEM,
            )
        floor_plan = self.repository.get_floor_plan(instrument.floor_plan_id)
        update_signal_branch_state(
            floor_plan,
            instrument.system_type,
            signal_instruments_status="draft",
            active_step="signal_instruments",
        )
        self.uow.commit()
        self.repository.refresh(instrument)
        return SignalInstrumentRecord.from_model(instrument)

    def delete_signal_instrument(self, instrument_id: int) -> None:
        instrument = self.repository.get_instrument(instrument_id)
        floor_plan_id = instrument.floor_plan_id
        self._migrate_legacy_common_branch_data(floor_plan_id)
        self.repository.delete(instrument)
        self.repository.flush()
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        update_signal_branch_state(
            floor_plan,
            COMMON_SIGNAL_BRANCH,
            signal_instruments_status="draft",
            soue_cables_status="draft" if self.repository.list_soue_devices(floor_plan_id, COMMON_SIGNAL_BRANCH) else "validated",
            active_step="signal_instruments",
        )
        for sps_system in SPS_SIGNAL_BRANCHES:
            fire_alarm_models = self.repository.list_fire_alarms(floor_plan_id, sps_system)
            update_signal_branch_state(
                floor_plan,
                sps_system,
                devices_cables_status="draft" if fire_alarm_models else "validated",
            )
        self.uow.commit()

    def commit_signal_instruments_step(self, floor_plan_id: int, system_type: str) -> None:
        normalized_system = self._normalize_system_type(system_type)
        self._migrate_legacy_common_branch_data(floor_plan_id)
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        instruments = self.repository.list_instruments(floor_plan_id, normalized_system)
        if not instruments:
            raise AppError(409, "instrument_required", "Add at least one instrument before saving the instrument step")
        if ensure_model_equipment_assignments(
            floor_plan,
            instruments,
            allowed_categories_getter=lambda instrument: SIGNAL_INSTRUMENT_CATEGORY_MAP.get(
                str(getattr(instrument, "instrument_type", "") or ""),
                (),
            ),
            entity_label_getter=lambda _instrument: "signal instrument",
        ):
            self.repository.flush()
        update_signal_branch_state(
            floor_plan,
            normalized_system,
            signal_instruments_status="validated",
            active_step="soue_devices",
        )
        self.uow.commit()

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return _normalize_common_signal_type(value)

    @staticmethod
    def _default_instrument_name(instrument_type: str, system_type: str) -> str:
        _ = system_type
        normalized_labels = {
            "control_panel": "Контрольный прибор",
            "loop_controller": "Контроллер шлейфа",
            "annunciator": "Оповещатель",
        }
        return normalized_labels.get(instrument_type, "Прибор")
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

    def _migrate_legacy_common_branch_data(self, floor_plan_id: int) -> None:
        common_instruments = self.repository.list_instruments(floor_plan_id, COMMON_SIGNAL_BRANCH)
        common_soue_devices = self.repository.list_soue_devices(floor_plan_id, COMMON_SIGNAL_BRANCH)
        common_soue_routes = self.repository.list_routes(floor_plan_id, COMMON_SIGNAL_BRANCH, SOUE_SUBSYSTEM)
        if common_instruments or common_soue_devices or common_soue_routes:
            return
        legacy_instruments = self.repository.list_instruments(floor_plan_id, "non_addressable")
        legacy_devices = self.repository.list_soue_devices(floor_plan_id, "non_addressable")
        legacy_routes = self.repository.list_routes(floor_plan_id, "non_addressable", SOUE_SUBSYSTEM)
        if not legacy_instruments and not legacy_devices and not legacy_routes:
            return
        for instrument in legacy_instruments:
            instrument.system_type = COMMON_SIGNAL_BRANCH
        for device in legacy_devices:
            device.system_type = COMMON_SIGNAL_BRANCH
        for route in legacy_routes:
            route.system_type = COMMON_SIGNAL_BRANCH
        self.repository.flush()

    def list_cable_routes(
        self,
        floor_plan_id: int,
        system_type: str | None = None,
        subsystem_type: str | None = None,
    ) -> list[CableRouteRecord]:
        normalized_subsystem = self._normalize_subsystem_type(subsystem_type) if subsystem_type else None
        if normalized_subsystem == SOUE_SUBSYSTEM:
            self._migrate_legacy_common_branch_data(floor_plan_id)
        normalized_system = (
            self._normalize_route_system_type(system_type, normalized_subsystem)
            if (system_type is not None or normalized_subsystem == SOUE_SUBSYSTEM)
            else None
        )
        return [
            CableRouteRecord.from_model(route)
            for route in self.repository.list_routes(floor_plan_id, normalized_system, normalized_subsystem)
        ]

    def recalculate_routes(
        self,
        floor_plan_id: int,
        system_type: str,
        subsystem_type: str = SPS_SUBSYSTEM,
        use_shared_trunk: bool = False,
    ) -> list[CableRouteRecord]:
        normalized_subsystem = self._normalize_subsystem_type(subsystem_type)
        route_system_type = self._normalize_route_system_type(system_type, normalized_subsystem)
        self._migrate_legacy_common_branch_data(floor_plan_id)
        instruments = self.repository.list_instruments(floor_plan_id, COMMON_SIGNAL_BRANCH)
        if not instruments:
            raise AppError(404, "instrument_not_found", "Signal instrument not found")
        branch_devices = self._list_branch_devices(floor_plan_id, route_system_type, normalized_subsystem)
        device_by_id = {int(device.id): device for device in branch_devices if device.id is not None}
        existing_routes = self.repository.list_routes(floor_plan_id, route_system_type, normalized_subsystem)
        assigned_by_instrument: dict[int, list[Any]] = {int(instrument.id): [] for instrument in instruments if instrument.id is not None}
        if len(instruments) == 1:
            assigned_by_instrument[int(instruments[0].id)] = branch_devices
        else:
            for route in existing_routes:
                if route.instrument_id not in assigned_by_instrument:
                    continue
                seen: set[int] = set()
                for device_id in route.device_ids or []:
                    safe_device_id = int(device_id)
                    if safe_device_id <= 0 or safe_device_id in seen or safe_device_id not in device_by_id:
                        continue
                    assigned_by_instrument[route.instrument_id].append(device_by_id[safe_device_id])
                    seen.add(safe_device_id)
        for instrument in instruments:
            instrument_id = int(instrument.id)
            if len(instruments) == 1:
                assigned_devices = branch_devices
            else:
                assigned_devices = assigned_by_instrument.get(instrument_id, [])
            self._replace_routes_for_instrument(
                instrument,
                route_system_type=route_system_type,
                subsystem_type=normalized_subsystem,
                use_shared_trunk=use_shared_trunk,
                assigned_device_models=assigned_devices,
            )
        self._sync_branch_routes_and_metadata(
            floor_plan_id,
            route_system_type,
            subsystem_type=normalized_subsystem,
        )
        self.uow.commit()
        self.events.publish(
            "cable_routes_recalculated",
            {
                "category": "signal_design",
                "use_case": "RecalculateCableRoutes",
                "floor_plan_id": floor_plan_id,
                "system_type": route_system_type,
                "subsystem_type": normalized_subsystem,
            },
        )
        return [
            CableRouteRecord.from_model(route)
            for route in self.repository.list_routes(floor_plan_id, route_system_type, normalized_subsystem)
        ]

    def merge_routes_for_instrument(
        self,
        instrument_id: int,
        device_ids: list[int],
        subsystem_type: str = SPS_SUBSYSTEM,
        system_type: str | None = None,
    ) -> list[CableRouteRecord]:
        instrument = self.repository.get_instrument(instrument_id)
        normalized_subsystem = self._normalize_subsystem_type(subsystem_type)
        floor_plan_id = int(instrument.floor_plan_id)
        route_system_type = self._normalize_route_system_type(system_type, normalized_subsystem)
        self._migrate_legacy_common_branch_data(floor_plan_id)
        branch_devices = self._list_branch_devices(floor_plan_id, route_system_type, normalized_subsystem)
        device_by_id = {
            int(device.id): device
            for device in branch_devices
            if device.id is not None
        }
        selected_ids = {
            int(device_id)
            for device_id in device_ids
            if int(device_id) in device_by_id
        }
        branch_routes = self.repository.list_routes(floor_plan_id, route_system_type, normalized_subsystem)
        assigned_by_instrument: dict[int, list[int]] = {}
        affected_instrument_ids = {int(instrument.id)}
        for route in branch_routes:
            current_ids = [
                int(device_id)
                for device_id in (route.device_ids or [])
                if int(device_id) > 0 and int(device_id) in device_by_id
            ]
            if not current_ids and route.instrument_id != instrument.id:
                continue
            remaining_ids = [device_id for device_id in current_ids if device_id not in selected_ids]
            if len(remaining_ids) != len(current_ids):
                affected_instrument_ids.add(int(route.instrument_id))
            assigned_by_instrument.setdefault(int(route.instrument_id), [])
            assigned_by_instrument[int(route.instrument_id)].extend(remaining_ids)
        assigned_by_instrument.setdefault(int(instrument.id), [])
        assigned_by_instrument[int(instrument.id)].extend(sorted(selected_ids))
        for current_instrument_id, assigned_ids in list(assigned_by_instrument.items()):
            deduped_ids: list[int] = []
            seen_ids: set[int] = set()
            for assigned_id in assigned_ids:
                if assigned_id in seen_ids:
                    continue
                seen_ids.add(assigned_id)
                deduped_ids.append(assigned_id)
            assigned_by_instrument[current_instrument_id] = deduped_ids
        affected_instrument_ids.update(
            current_instrument_id
            for current_instrument_id, assigned_ids in assigned_by_instrument.items()
            if not assigned_ids
        )
        for affected_instrument_id in affected_instrument_ids:
            current_instrument = self.repository.get_instrument(affected_instrument_id)
            assigned_device_models = [
                device_by_id[assigned_id]
                for assigned_id in assigned_by_instrument.get(affected_instrument_id, [])
                if assigned_id in device_by_id
            ]
            self._replace_routes_for_instrument(
                current_instrument,
                route_system_type=route_system_type,
                subsystem_type=normalized_subsystem,
                use_shared_trunk=False,
                assigned_device_models=assigned_device_models,
            )
        self._sync_branch_routes_and_metadata(floor_plan_id, route_system_type, subsystem_type=normalized_subsystem)
        self.uow.commit()
        self.events.publish(
            "instrument_routes_merged",
            {
                "category": "signal_design",
                "use_case": "MergeRoutesForInstrument",
                "floor_plan_id": floor_plan_id,
                "system_type": route_system_type,
                "subsystem_type": normalized_subsystem,
                "instrument_id": instrument_id,
            },
        )
        return [
            CableRouteRecord.from_model(route)
            for route in self.repository.list_routes(floor_plan_id, route_system_type, normalized_subsystem)
        ]

    def update_cable_route(self, route_id: int, payload) -> CableRouteRecord:
        route = self.repository.get_route(route_id)
        route.polyline_points = payload.polyline_points
        route.is_manual = payload.is_manual
        if should_show_zc_terminator(
            {
                "system_type": route.system_type,
                "route_kind": route.route_kind,
                "subsystem_type": route.subsystem_type,
            }
        ):
            if payload.zc_label_dx is not None:
                route.zc_label_dx = float(payload.zc_label_dx)
            if payload.zc_label_dy is not None:
                route.zc_label_dy = float(payload.zc_label_dy)
        else:
            route.zc_label_dx = None
            route.zc_label_dy = None
        floor_plan = self.repository.get_floor_plan(route.floor_plan_id)
        route.length_m = CableRoutingPolicy.length(route.polyline_points or [], floor_plan.scale_factor)
        self._sync_branch_routes_and_metadata(
            route.floor_plan_id,
            route.system_type,
            floor_plan=floor_plan,
            subsystem_type=self._normalize_subsystem_type(route.subsystem_type),
        )
        self.uow.commit()
        self.repository.refresh(route)
        return CableRouteRecord.from_model(route)

    def _replace_routes_for_instrument(
        self,
        instrument,
        *,
        route_system_type: str,
        subsystem_type: str,
        use_shared_trunk: bool,
        assigned_device_models: list[Any] | None = None,
    ) -> None:
        floor_plan = self.repository.get_floor_plan(instrument.floor_plan_id)
        device_models = assigned_device_models if assigned_device_models is not None else self._list_branch_devices(
            instrument.floor_plan_id,
            route_system_type,
            subsystem_type,
        )
        devices = [device.to_dict() for device in device_models]
        routes = CableRoutingPolicy.recalculate(
            floor_plan.to_dict(include_elements=True),
            system_type=route_system_type,
            instrument={**instrument.to_dict(), "system_type": route_system_type},
            alarms=devices,
            use_shared_trunk=use_shared_trunk and instrument.supports_cable_merge,
            subsystem_type=subsystem_type,
        )
        self.repository.delete_routes_for_instrument(instrument.id, subsystem_type=subsystem_type)
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

    def _sync_branch_routes_and_metadata(
        self,
        floor_plan_id: int,
        system_type: str,
        *,
        floor_plan=None,
        subsystem_type: str = SPS_SUBSYSTEM,
        fire_alarms_status: str | None = None,
        soue_devices_status: str | None = None,
        active_step: str | None = None,
    ) -> None:
        normalized_system = self._normalize_system_type(system_type)
        normalized_subsystem = self._normalize_subsystem_type(subsystem_type)
        branch_routes = self.repository.list_routes(floor_plan_id, normalized_system, normalized_subsystem)
        route_sort_key = lambda route: (
            ROUTE_KIND_ORDER.get(str(route.route_kind or ""), 99),
            int(route.instrument_id or 0),
            int(route.route_number or 0),
            int(route.id or 0),
        )
        normalized_payloads = normalize_branch_route_numbers([route.to_dict() for route in branch_routes])
        normalized_numbers_by_id = {
            int(payload["id"]): int(payload["route_number"])
            for payload in normalized_payloads
            if payload.get("id") is not None
        }
        for route in sorted(branch_routes, key=route_sort_key):
            if route.id is not None and int(route.id) in normalized_numbers_by_id:
                route.route_number = normalized_numbers_by_id[int(route.id)]
        metadata = build_device_route_metadata(
            [route.to_dict() for route in sorted(branch_routes, key=route_sort_key)],
            system_type=normalized_system,
        )
        floor_plan_model = floor_plan or self.repository.get_floor_plan(floor_plan_id)
        branch_devices = self._list_branch_devices(floor_plan_id, normalized_system, normalized_subsystem)
        if ensure_model_equipment_assignments(
            floor_plan_model,
            branch_devices,
            allowed_categories_getter=(
                lambda device: SOUE_DEVICE_CATEGORY_MAP.get(str(getattr(device, "device_type", "") or ""), ())
                if normalized_subsystem == SOUE_SUBSYSTEM
                else FIRE_ALARM_DEVICE_CATEGORY_MAP.get(str(getattr(device, "device_type", "") or ""), ())
            ),
            entity_label_getter=lambda _device: "SOUE device" if normalized_subsystem == SOUE_SUBSYSTEM else "fire alarm device",
        ):
            self.repository.flush()
        for device in branch_devices:
            if device.id is None or int(device.id) not in metadata:
                device.loop_kind = None
                device.loop_number = None
                device.device_number = None
                if hasattr(device, "address"):
                    device.address = None
                continue
            update = metadata[int(device.id)]
            device.loop_kind = update["loop_kind"]
            device.loop_number = update["loop_number"]
            device.device_number = update["device_number"]
            if hasattr(device, "address"):
                device.address = update["address"]
        assigned_device_ids = {device_id for device_id in metadata}
        if normalized_subsystem == SPS_SUBSYSTEM:
            devices_cables_status = "validated"
            if any(device.id is not None and int(device.id) not in assigned_device_ids for device in branch_devices):
                devices_cables_status = "draft"
            update_signal_branch_state(
                floor_plan_model,
                normalized_system,
                fire_alarms_status=fire_alarms_status,
                devices_cables_status=devices_cables_status,
                active_step=active_step,
            )
            return
        soue_cables_status = "validated"
        if any(device.id is not None and int(device.id) not in assigned_device_ids for device in branch_devices):
            soue_cables_status = "draft"
        update_signal_branch_state(
            floor_plan_model,
            normalized_system,
            soue_devices_status=soue_devices_status,
            soue_cables_status=soue_cables_status,
            active_step=active_step,
        )

    def commit_routes_step(
        self,
        floor_plan_id: int,
        system_type: str,
        subsystem_type: str = SPS_SUBSYSTEM,
    ) -> None:
        normalized_subsystem = self._normalize_subsystem_type(subsystem_type)
        normalized_system = self._normalize_route_system_type(system_type, normalized_subsystem)
        if normalized_subsystem == SOUE_SUBSYSTEM:
            self._migrate_legacy_common_branch_data(floor_plan_id)
        next_step = "devices_cables" if normalized_subsystem == SPS_SUBSYSTEM else "soue_cables"
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        self._sync_branch_routes_and_metadata(
            floor_plan_id,
            normalized_system,
            floor_plan=floor_plan,
            subsystem_type=normalized_subsystem,
            active_step=next_step,
        )
        branch_state = (
            floor_plan.pipeline_state.get("branches", {})
            .get(normalized_system, {})
            .get("steps", {})
        )
        status_key = "devices_cables" if normalized_subsystem == SPS_SUBSYSTEM else "soue_cables"
        step_status = str((branch_state.get(status_key) or {}).get("status") or "locked")
        branch_devices = self._list_branch_devices(floor_plan_id, normalized_system, normalized_subsystem)
        if branch_devices and step_status != "validated":
            raise AppError(409, "cable_routes_incomplete", "Assign all branch devices to cable routes before saving the cable step")
        self.uow.commit()

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {*SPS_SIGNAL_BRANCHES, COMMON_SIGNAL_BRANCH} else "non_addressable"

    @staticmethod
    def _normalize_route_system_type(value: str | None, subsystem_type: str | None) -> str:
        if subsystem_type == SOUE_SUBSYSTEM:
            return COMMON_SIGNAL_BRANCH
        return _normalize_sps_system_type(value)

    @staticmethod
    def _normalize_subsystem_type(value: str | None) -> str:
        return SOUE_SUBSYSTEM if value == SOUE_SUBSYSTEM else SPS_SUBSYSTEM

    def _list_branch_devices(self, floor_plan_id: int, system_type: str, subsystem_type: str) -> list[Any]:
        if subsystem_type == SOUE_SUBSYSTEM:
            return self.repository.list_soue_devices(floor_plan_id, system_type)
        return self.repository.list_fire_alarms(floor_plan_id, system_type)


class SignalDesignUseCases:
    """Composition root for signal design use cases."""

    def __init__(self, repository: SignalDesignRepository, uow: UnitOfWork, events: Any | None = None):
        publisher = events or NoOpEventPublisher()
        self.zkspc = ZkspcUseCases(repository, uow, publisher)
        self.fire_alarm_layout = FireAlarmLayoutUseCases(repository, uow, publisher)
        self.soue_layout = SoueLayoutUseCases(repository, uow, publisher)
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

    def list_soue_devices(self, floor_plan_id: int, system_type: str | None = None) -> list[SoueDeviceRecord]:
        return self.soue_layout.list_soue_devices(floor_plan_id, system_type)

    def auto_layout_soue_devices(self, floor_plan_id: int, system_type: str) -> dict[str, Any]:
        return self.soue_layout.auto_layout_soue_devices(floor_plan_id, system_type)

    def replace_branch_soue_devices(self, floor_plan_id: int, system_type: str, payloads: list[dict[str, Any]]) -> None:
        self.soue_layout.replace_branch_soue_devices(floor_plan_id, system_type, payloads)

    def list_signal_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentRecord]:
        return self.instruments.list_signal_instruments(floor_plan_id, system_type)

    def create_signal_instrument(self, payload) -> SignalInstrumentRecord:
        return self.instruments.create_signal_instrument(payload)

    def update_signal_instrument(self, instrument_id: int, payload) -> SignalInstrumentRecord:
        return self.instruments.update_signal_instrument(instrument_id, payload)

    def delete_signal_instrument(self, instrument_id: int) -> None:
        self.instruments.delete_signal_instrument(instrument_id)

    def commit_signal_instruments_step(self, floor_plan_id: int, system_type: str) -> None:
        self.instruments.commit_signal_instruments_step(floor_plan_id, system_type)

    def list_cable_routes(
        self,
        floor_plan_id: int,
        system_type: str | None = None,
        subsystem_type: str | None = None,
    ) -> list[CableRouteRecord]:
        return self.cable_routing.list_cable_routes(floor_plan_id, system_type, subsystem_type)

    def recalculate_routes(
        self,
        floor_plan_id: int,
        system_type: str,
        subsystem_type: str = SPS_SUBSYSTEM,
        use_shared_trunk: bool = False,
    ) -> list[CableRouteRecord]:
        return self.cable_routing.recalculate_routes(floor_plan_id, system_type, subsystem_type, use_shared_trunk)

    def update_cable_route(self, route_id: int, payload) -> CableRouteRecord:
        return self.cable_routing.update_cable_route(route_id, payload)

    def merge_routes_for_instrument(
        self,
        instrument_id: int,
        device_ids: list[int],
        subsystem_type: str = SPS_SUBSYSTEM,
        system_type: str | None = None,
    ) -> list[CableRouteRecord]:
        return self.cable_routing.merge_routes_for_instrument(instrument_id, device_ids, subsystem_type, system_type)

    def commit_routes_step(
        self,
        floor_plan_id: int,
        system_type: str,
        subsystem_type: str = SPS_SUBSYSTEM,
    ) -> None:
        self.cable_routing.commit_routes_step(floor_plan_id, system_type, subsystem_type)

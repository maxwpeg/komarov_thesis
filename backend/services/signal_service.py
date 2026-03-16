"""Signal planning application service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.fire_alarm_placement import calculate_fire_alarm_layout, locate_fire_alarm_metadata
from backend.models import (
    CableRoute as CableRouteModel,
    FireAlarm as FireAlarmModel,
    FloorPlan as FloorPlanModel,
    Room as RoomModel,
    SignalInstrument as SignalInstrumentModel,
    ZkspcZone as ZkspcZoneModel,
    ZkspcZoneRoom as ZkspcZoneRoomModel,
)
from backend.schemas import (
    CableRouteUpdate,
    SignalInstrumentCreate,
    SignalInstrumentUpdate,
    ZkspcZoneCommit,
)
from backend.signal_planning import (
    MERGE_CAPABLE_INSTRUMENTS,
    calculate_zkspc_layout,
    recalculate_cable_routes,
    route_length_m,
)
from backend.services.pipeline_state_helpers import update_signal_branch_state


class SignalService:
    """Handles ZKSPC zones, branch-specific fire alarms, instruments and cable routes."""

    def __init__(self, db: Session):
        self.db = db

    def list_zkspc_zones(self, floor_plan_id: int) -> list[ZkspcZoneModel]:
        return (
            self.db.query(ZkspcZoneModel)
            .filter(ZkspcZoneModel.floor_plan_id == floor_plan_id)
            .order_by(ZkspcZoneModel.zone_number.asc(), ZkspcZoneModel.id.asc())
            .all()
        )

    def detect_zkspc(self, floor_plan_id: int) -> list[ZkspcZoneModel]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        zones = calculate_zkspc_layout([room.to_dict() for room in floor_plan.rooms])
        return self.replace_zkspc_zones(
            floor_plan_id,
            [ZkspcZoneCommit.model_validate({**zone, "id": None}) for zone in zones],
        )

    def replace_zkspc_zones(self, floor_plan_id: int, zones: list[ZkspcZoneCommit]) -> list[ZkspcZoneModel]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        room_map = {room.id: room for room in floor_plan.rooms}

        existing_zone_ids = [zone.id for zone in self.list_zkspc_zones(floor_plan_id)]
        if existing_zone_ids:
            self.db.query(ZkspcZoneRoomModel).filter(ZkspcZoneRoomModel.zone_id.in_(existing_zone_ids)).delete(  # type: ignore[arg-type]
                synchronize_session=False
            )
            self.db.query(ZkspcZoneModel).filter(ZkspcZoneModel.id.in_(existing_zone_ids)).delete(  # type: ignore[arg-type]
                synchronize_session=False
            )
            self.db.flush()

        created: list[ZkspcZoneModel] = []
        for index, zone_payload in enumerate(zones, start=1):
            room_ids = [int(room_id) for room_id in zone_payload.room_ids if int(room_id) in room_map]
            rooms = [room_map[room_id] for room_id in room_ids]
            area_sqm = round(sum(float(room.area_sqm or 0.0) for room in rooms), 2)
            warnings = [
                "Пожарные отсеки, номера и расстояния между изолированными выходами требуют ручной проверки.",
            ]
            if len(room_ids) > 5:
                warnings.append("В ЗКСПС более 5 помещений.")
            if area_sqm > 2000.0:
                warnings.append("Площадь ЗКСПС превышает 2000 м2.")
            zone = ZkspcZoneModel(
                floor_plan_id=floor_plan_id,
                zone_number=zone_payload.zone_number or index,
                name=(zone_payload.name or f"ЗКСПС {zone_payload.zone_number or index}").strip(),
                area_sqm=area_sqm,
                room_count=len(room_ids),
                is_manual=zone_payload.is_manual,
                is_locked=zone_payload.is_locked,
                compliance_warnings=warnings,
            )
            self.db.add(zone)
            self.db.flush()
            for room_id in room_ids:
                self.db.add(ZkspcZoneRoomModel(zone_id=zone.id, room_id=room_id))
            created.append(zone)

        self.db.flush()
        self._refresh_fire_alarm_zone_assignments(floor_plan_id)
        self.db.commit()
        return self.list_zkspc_zones(floor_plan_id)

    def auto_layout_fire_alarms(self, floor_plan_id: int, system_type: str) -> dict[str, Any]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        plan_data = floor_plan.to_dict(include_elements=True)
        zones = [zone.to_dict() for zone in self.list_zkspc_zones(floor_plan_id)]
        return calculate_fire_alarm_layout(
            plan_data,
            scale_factor=floor_plan.scale_factor,
            system_type=system_type,
            zkspc_zones=zones,
        )

    def replace_branch_fire_alarms(self, floor_plan_id: int, system_type: str, payloads: list[dict[str, Any]]) -> None:
        normalized_system = self._normalize_system_type(system_type)
        floor_plan = self._get_floor_plan(floor_plan_id)
        self.db.query(FireAlarmModel).filter(
            FireAlarmModel.floor_plan_id == floor_plan_id,
            FireAlarmModel.system_type == normalized_system,
        ).delete(synchronize_session=False)
        for payload in payloads:
            normalized = self._normalize_fire_alarm_payload(
                floor_plan_id,
                {
                    "floor_plan_id": floor_plan_id,
                    "system_type": normalized_system,
                    **payload,
                },
            )
            self.db.add(FireAlarmModel(**normalized))
        update_signal_branch_state(
            floor_plan,
            normalized_system,
            fire_alarms_status="validated",
            devices_cables_status="draft",
            active_step="devices_cables",
        )
        self.db.commit()

    def list_signal_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentModel]:
        query = self.db.query(SignalInstrumentModel).filter(SignalInstrumentModel.floor_plan_id == floor_plan_id)
        if system_type:
            query = query.filter(SignalInstrumentModel.system_type == self._normalize_system_type(system_type))
        return query.order_by(SignalInstrumentModel.id.asc()).all()

    def create_signal_instrument(self, payload: SignalInstrumentCreate) -> SignalInstrumentModel:
        system_type = self._normalize_system_type(payload.system_type)
        floor_plan = self._get_floor_plan(payload.floor_plan_id)
        existing = self.list_signal_instruments(payload.floor_plan_id, system_type)
        if existing:
            raise AppError(409, "instrument_limit_reached", "Only one primary instrument per system is supported")
        instrument = SignalInstrumentModel(
            floor_plan_id=payload.floor_plan_id,
            system_type=system_type,
            instrument_type=payload.instrument_type,
            x=float(payload.x),
            y=float(payload.y),
            name=payload.name or self._default_instrument_name(payload.instrument_type, system_type),
            supports_cable_merge=(
                payload.supports_cable_merge
                if payload.supports_cable_merge is not None
                else payload.instrument_type in MERGE_CAPABLE_INSTRUMENTS
            ),
        )
        self.db.add(instrument)
        self.db.flush()
        self._replace_routes_for_instrument(instrument, use_shared_trunk=False)
        update_signal_branch_state(
            floor_plan,
            system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.db.commit()
        self.db.refresh(instrument)
        return instrument

    def update_signal_instrument(self, instrument_id: int, payload: SignalInstrumentUpdate) -> SignalInstrumentModel:
        instrument = self._get_instrument(instrument_id)
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
        self.db.flush()
        self._replace_routes_for_instrument(instrument, use_shared_trunk=False)
        update_signal_branch_state(
            self._get_floor_plan(instrument.floor_plan_id),
            instrument.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.db.commit()
        self.db.refresh(instrument)
        return instrument

    def delete_signal_instrument(self, instrument_id: int) -> None:
        instrument = self._get_instrument(instrument_id)
        floor_plan = self._get_floor_plan(instrument.floor_plan_id)
        system_type = instrument.system_type
        self.db.delete(instrument)
        update_signal_branch_state(
            floor_plan,
            system_type,
            devices_cables_status="draft",
            active_step="fire_alarms",
        )
        self.db.commit()

    def list_cable_routes(self, floor_plan_id: int, system_type: str | None = None) -> list[CableRouteModel]:
        query = self.db.query(CableRouteModel).filter(CableRouteModel.floor_plan_id == floor_plan_id)
        if system_type:
            query = query.filter(CableRouteModel.system_type == self._normalize_system_type(system_type))
        return query.order_by(CableRouteModel.route_kind.asc(), CableRouteModel.route_number.asc(), CableRouteModel.id.asc()).all()

    def recalculate_routes(self, floor_plan_id: int, system_type: str, use_shared_trunk: bool = False) -> list[CableRouteModel]:
        instrument = self._require_single_instrument(floor_plan_id, system_type)
        self._replace_routes_for_instrument(instrument, use_shared_trunk=use_shared_trunk)
        update_signal_branch_state(
            self._get_floor_plan(floor_plan_id),
            instrument.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.db.commit()
        return self.list_cable_routes(floor_plan_id, system_type)

    def update_cable_route(self, route_id: int, payload: CableRouteUpdate) -> CableRouteModel:
        route = self._get_cable_route(route_id)
        route.polyline_points = payload.polyline_points
        route.is_manual = payload.is_manual
        floor_plan = self._get_floor_plan(route.floor_plan_id)
        route.length_m = route_length_m(route.polyline_points or [], floor_plan.scale_factor)
        update_signal_branch_state(
            floor_plan,
            route.system_type,
            devices_cables_status="validated",
            active_step="devices_cables",
        )
        self.db.commit()
        self.db.refresh(route)
        return route

    def _replace_routes_for_instrument(self, instrument: SignalInstrumentModel, *, use_shared_trunk: bool) -> None:
        floor_plan = self._get_floor_plan(instrument.floor_plan_id)
        alarms = [
            alarm.to_dict()
            for alarm in floor_plan.fire_alarms
            if alarm.system_type == instrument.system_type
        ]
        routes = recalculate_cable_routes(
            floor_plan.to_dict(include_elements=True),
            system_type=instrument.system_type,
            instrument=instrument.to_dict(),
            alarms=alarms,
            use_shared_trunk=use_shared_trunk and instrument.supports_cable_merge,
        )
        self.db.query(CableRouteModel).filter(CableRouteModel.instrument_id == instrument.id).delete(synchronize_session=False)
        for route_payload in routes:
            self.db.add(CableRouteModel(floor_plan_id=instrument.floor_plan_id, **route_payload))
        self.db.flush()

    def _refresh_fire_alarm_zone_assignments(self, floor_plan_id: int) -> None:
        zones = self.list_zkspc_zones(floor_plan_id)
        room_to_zone: dict[int, ZkspcZoneModel] = {}
        for zone in zones:
            for room_id in [link.room_id for link in zone.room_links]:
                room_to_zone[int(room_id)] = zone
        for alarm in self.db.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id).all():
            zone = room_to_zone.get(int(alarm.room_id)) if alarm.room_id is not None and int(alarm.room_id) in room_to_zone else None
            alarm.zkspc_zone_id = zone.id if zone is not None else None
            alarm.zone = str(zone.zone_number) if zone is not None else None

    def _normalize_fire_alarm_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in floor_plan.rooms]
        x = float(data["x"])
        y = float(data["y"])
        metadata = locate_fire_alarm_metadata(x, y, rooms, floor_plan.scale_factor or 1.0)

        zone = None
        zkspc_zone_id = data.get("zkspc_zone_id")
        if metadata.get("room_id") is not None:
            room_zone = self._find_zone_for_room(floor_plan_id, int(metadata["room_id"]))
            if room_zone is not None:
                zkspc_zone_id = room_zone.id
                zone = str(room_zone.zone_number)

        return {
            **data,
            "floor_plan_id": floor_plan_id,
            "x": x,
            "y": y,
            "coverage_radius": float(data["coverage_radius"]) if data.get("coverage_radius") is not None else None,
            "mounting_height": float(data["mounting_height"]) if data.get("mounting_height") is not None else None,
            "system_type": self._normalize_system_type(data.get("system_type")),
            "zkspc_zone_id": int(zkspc_zone_id) if zkspc_zone_id is not None else None,
            "loop_number": int(data["loop_number"]) if data.get("loop_number") is not None else None,
            "device_number": int(data["device_number"]) if data.get("device_number") is not None else None,
            "loop_kind": data.get("loop_kind"),
            "zone": zone if zone is not None else data.get("zone"),
            "address": data.get("address"),
            **metadata,
        }

    def _find_zone_for_room(self, floor_plan_id: int, room_id: int) -> ZkspcZoneModel | None:
        for zone in self.list_zkspc_zones(floor_plan_id):
            if any(link.room_id == room_id for link in zone.room_links):
                return zone
        return None

    def _default_instrument_name(self, instrument_type: str, system_type: str) -> str:
        prefix = "Адресный" if system_type == "addressable" else "Безадресный"
        labels = {
            "control_panel": "контрольный прибор",
            "loop_controller": "контроллер шлейфа",
            "annunciator": "оповещатель",
        }
        return f"{prefix} {labels.get(instrument_type, 'прибор')}"

    def _require_single_instrument(self, floor_plan_id: int, system_type: str) -> SignalInstrumentModel:
        instruments = self.list_signal_instruments(floor_plan_id, system_type)
        if not instruments:
            raise AppError(404, "instrument_not_found", "Signal instrument not found")
        return instruments[0]

    def _get_floor_plan(self, floor_plan_id: int) -> FloorPlanModel:
        floor_plan = (
            self.db.query(FloorPlanModel)
            .filter(FloorPlanModel.id == floor_plan_id)
            .first()
        )
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    def _get_instrument(self, instrument_id: int) -> SignalInstrumentModel:
        instrument = self.db.query(SignalInstrumentModel).filter(SignalInstrumentModel.id == instrument_id).first()
        if instrument is None:
            raise AppError(404, "instrument_not_found", "Signal instrument not found")
        return instrument

    def _get_cable_route(self, route_id: int) -> CableRouteModel:
        route = self.db.query(CableRouteModel).filter(CableRouteModel.id == route_id).first()
        if route is None:
            raise AppError(404, "cable_route_not_found", "Cable route not found")
        return route

    @staticmethod
    def _normalize_system_type(value: str | None) -> str:
        return value if value in {"addressable", "non_addressable"} else "non_addressable"

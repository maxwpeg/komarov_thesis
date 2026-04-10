"""SQLAlchemy repositories for signal design."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import (
    CableRoute as CableRouteModel,
    FireAlarm as FireAlarmModel,
    FloorPlan as FloorPlanModel,
    SignalInstrument as SignalInstrumentModel,
    ZkspcZone as ZkspcZoneModel,
    ZkspcZoneRoom as ZkspcZoneRoomModel,
)
from backend.modules.signal_design.ports.repositories import SignalDesignRepository


class SqlAlchemySignalDesignRepository(SignalDesignRepository):
    """SQLAlchemy-backed repository for signal design aggregates."""

    def __init__(self, session: Session):
        self.session = session

    def get_floor_plan(self, floor_plan_id: int) -> FloorPlanModel:
        floor_plan = self.session.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    def get_instrument(self, instrument_id: int) -> SignalInstrumentModel:
        instrument = self.session.query(SignalInstrumentModel).filter(SignalInstrumentModel.id == instrument_id).first()
        if instrument is None:
            raise AppError(404, "instrument_not_found", "Signal instrument not found")
        return instrument

    def get_route(self, route_id: int) -> CableRouteModel:
        route = self.session.query(CableRouteModel).filter(CableRouteModel.id == route_id).first()
        if route is None:
            raise AppError(404, "cable_route_not_found", "Cable route not found")
        return route

    def list_zones(self, floor_plan_id: int) -> list[ZkspcZoneModel]:
        return (
            self.session.query(ZkspcZoneModel)
            .filter(ZkspcZoneModel.floor_plan_id == floor_plan_id)
            .order_by(ZkspcZoneModel.zone_number.asc(), ZkspcZoneModel.id.asc())
            .all()
        )

    def list_instruments(self, floor_plan_id: int, system_type: str | None = None) -> list[SignalInstrumentModel]:
        query = self.session.query(SignalInstrumentModel).filter(SignalInstrumentModel.floor_plan_id == floor_plan_id)
        if system_type:
            query = query.filter(SignalInstrumentModel.system_type == system_type)
        return query.order_by(SignalInstrumentModel.id.asc()).all()

    def list_routes(self, floor_plan_id: int, system_type: str | None = None) -> list[CableRouteModel]:
        query = self.session.query(CableRouteModel).filter(CableRouteModel.floor_plan_id == floor_plan_id)
        if system_type:
            query = query.filter(CableRouteModel.system_type == system_type)
        return query.order_by(CableRouteModel.route_kind.asc(), CableRouteModel.route_number.asc(), CableRouteModel.id.asc()).all()

    def list_fire_alarms(self, floor_plan_id: int, system_type: str | None = None) -> list[FireAlarmModel]:
        query = self.session.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id)
        if system_type:
            query = query.filter(FireAlarmModel.system_type == system_type)
        return query.order_by(FireAlarmModel.id.asc()).all()

    def create_zone(self, data: dict) -> ZkspcZoneModel:
        return ZkspcZoneModel(**data)

    def create_zone_room(self, zone_id: int, room_id: int) -> ZkspcZoneRoomModel:
        return ZkspcZoneRoomModel(zone_id=zone_id, room_id=room_id)

    def create_fire_alarm(self, data: dict) -> FireAlarmModel:
        return FireAlarmModel(**data)

    def create_instrument(self, data: dict) -> SignalInstrumentModel:
        return SignalInstrumentModel(**data)

    def create_route(self, data: dict) -> CableRouteModel:
        return CableRouteModel(**data)

    def add(self, entity) -> None:
        self.session.add(entity)

    def delete(self, entity) -> None:
        self.session.delete(entity)

    def flush(self) -> None:
        self.session.flush()

    def refresh(self, entity) -> None:
        self.session.refresh(entity)

    def delete_routes_for_instrument(self, instrument_id: int) -> None:
        self.session.query(CableRouteModel).filter(CableRouteModel.instrument_id == instrument_id).delete(synchronize_session=False)

    def delete_routes_for_branch(self, floor_plan_id: int, system_type: str) -> None:
        self.session.query(CableRouteModel).filter(
            CableRouteModel.floor_plan_id == floor_plan_id,
            CableRouteModel.system_type == system_type,
        ).delete(synchronize_session=False)

    def delete_zones_for_floor_plan(self, floor_plan_id: int) -> None:
        existing_zone_ids = [zone.id for zone in self.list_zones(floor_plan_id)]
        if existing_zone_ids:
            self.session.query(ZkspcZoneRoomModel).filter(ZkspcZoneRoomModel.zone_id.in_(existing_zone_ids)).delete(synchronize_session=False)  # type: ignore[arg-type]
            self.session.query(ZkspcZoneModel).filter(ZkspcZoneModel.id.in_(existing_zone_ids)).delete(synchronize_session=False)  # type: ignore[arg-type]

    def delete_fire_alarms_for_branch(self, floor_plan_id: int, system_type: str) -> None:
        self.session.query(FireAlarmModel).filter(
            FireAlarmModel.floor_plan_id == floor_plan_id,
            FireAlarmModel.system_type == system_type,
        ).delete(synchronize_session=False)

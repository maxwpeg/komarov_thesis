"""Mapping helpers from persistence or domain records to API schemas."""

from __future__ import annotations

from typing import Any

from backend import schemas
from backend.models import (
    CableRoute,
    Dimension,
    Door,
    EquipmentItem,
    FireAlarm,
    FloorPlan,
    FloorplanRecognition,
    Project,
    ProjectEquipmentSelection,
    Room,
    SoueDevice,
    SignalInstrument,
    Stair,
    Wall,
    Window,
    ZkspcZone,
)


def _payload(instance: Any, **kwargs) -> dict[str, Any]:
    to_dict = getattr(instance, "to_dict", None)
    if to_dict is None:
        raise TypeError(f"Unsupported object for schema mapping: {type(instance)!r}")
    try:
        return to_dict(**kwargs)
    except TypeError:
        return to_dict()


def project_read(project: Project) -> schemas.ProjectRead:
    return schemas.ProjectRead.model_validate(_payload(project))


def equipment_item_read(item: EquipmentItem) -> schemas.EquipmentItemRead:
    return schemas.EquipmentItemRead.model_validate(_payload(item))


def project_equipment_selections_read(selections: ProjectEquipmentSelection | Any) -> schemas.ProjectEquipmentSelectionsRead:
    return schemas.ProjectEquipmentSelectionsRead.model_validate(_payload(selections))


def project_equipment_list_read(project_id: int, items: list[Any]) -> schemas.ProjectEquipmentListRead:
    return schemas.ProjectEquipmentListRead(
        project_id=project_id,
        items=[equipment_item_read(item) for item in items],
    )


def equipment_specification_read(specification: dict[str, Any]) -> schemas.EquipmentSpecificationRead:
    return schemas.EquipmentSpecificationRead.model_validate(specification)


def power_consumption_calculation_read(
    calculation: dict[str, Any],
) -> schemas.PowerConsumptionCalculationRead:
    return schemas.PowerConsumptionCalculationRead.model_validate(calculation)


def general_instructions_read(payload: dict[str, Any]) -> schemas.GeneralInstructionsRead:
    return schemas.GeneralInstructionsRead.model_validate(payload)


def general_data_read(payload: dict[str, Any]) -> schemas.GeneralDataRead:
    return schemas.GeneralDataRead.model_validate(payload)


def additional_info_read(payload: dict[str, Any]) -> schemas.AdditionalInfoRead:
    return schemas.AdditionalInfoRead.model_validate(payload)


def wall_read(wall: Wall) -> schemas.WallRead:
    return schemas.WallRead.model_validate(wall.to_dict())


def door_read(door: Door) -> schemas.DoorRead:
    return schemas.DoorRead.model_validate(door.to_dict())


def stair_read(stair: Stair) -> schemas.StairRead:
    return schemas.StairRead.model_validate(stair.to_dict())


def window_read(window: Window) -> schemas.WindowRead:
    return schemas.WindowRead.model_validate(window.to_dict())


def room_read(room: Room) -> schemas.RoomRead:
    return schemas.RoomRead.model_validate(room.to_dict())


def dimension_read(dimension: Dimension) -> schemas.DimensionRead:
    return schemas.DimensionRead.model_validate(dimension.to_dict())


def fire_alarm_read(fire_alarm: FireAlarm) -> schemas.FireAlarmRead:
    return schemas.FireAlarmRead.model_validate(fire_alarm.to_dict())


def soue_device_read(device: SoueDevice) -> schemas.SoueDeviceRead:
    return schemas.SoueDeviceRead.model_validate(device.to_dict())


def zkspc_zone_read(zone: ZkspcZone) -> schemas.ZkspcZoneRead:
    return schemas.ZkspcZoneRead.model_validate(zone.to_dict())


def signal_instrument_read(instrument: SignalInstrument) -> schemas.SignalInstrumentRead:
    return schemas.SignalInstrumentRead.model_validate(instrument.to_dict())


def cable_route_read(route: CableRoute) -> schemas.CableRouteRead:
    return schemas.CableRouteRead.model_validate(route.to_dict())


def floor_plan_read(floor_plan: FloorPlan, include_elements: bool = False) -> schemas.FloorPlanRead:
    return schemas.FloorPlanRead.model_validate(_payload(floor_plan, include_elements=include_elements))


def recognition_read(recognition: FloorplanRecognition) -> schemas.RecognitionRead:
    return schemas.RecognitionRead.model_validate(recognition.to_dict())

"""Mapping helpers from persistence or domain records to API schemas."""

from __future__ import annotations

from typing import Any

from backend import schemas
from backend.assets import build_asset_url
from backend.models import (
    BackgroundTask,
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
        payload = to_dict(**kwargs)
    except TypeError:
        payload = to_dict()
    return _inject_asset_urls(payload)


def _inject_asset_urls(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    if "latest_pdf_path" in data:
        data["latest_pdf_url"] = build_asset_url(data.get("latest_pdf_path"))
    if "image_path" in data:
        data["image_url"] = build_asset_url(data.get("image_path"))
    if "label_pdf_path" in data:
        data["label_pdf_url"] = build_asset_url(data.get("label_pdf_path"))
    if "manual_pdf_path" in data:
        data["manual_pdf_url"] = build_asset_url(data.get("manual_pdf_path"))
    if "original_image_path" in data:
        data["original_image_url"] = build_asset_url(data.get("original_image_path"))
    if "processed_image_path" in data:
        data["processed_image_url"] = build_asset_url(data.get("processed_image_path"))
    if "debug_artifacts_dir" in data:
        data["debug_artifacts_url"] = build_asset_url(data.get("debug_artifacts_dir"))
    if "log_path" in data:
        data["log_url"] = build_asset_url(data.get("log_path"))
    return data


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
    return schemas.RecognitionRead.model_validate(_payload(recognition))


def background_task_read(task: BackgroundTask) -> schemas.BackgroundTaskRead:
    return schemas.BackgroundTaskRead.model_validate(_payload(task))

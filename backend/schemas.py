"""Pydantic schemas for the backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base API model."""

    model_config = ConfigDict(from_attributes=True)


SignalSystemType = Literal["addressable", "non_addressable"]
WallAlignment = Literal["center", "left", "right"]


class ProjectCreate(APIModel):
    name: str
    project_type: str = "PS"
    year: int = Field(default_factory=lambda: datetime.now().year)
    contractor: str
    engineer: str
    cpe: str
    checker: str
    facility: str
    facility_address: str | None = None
    project_description: str | None = None
    stage: str = "R"
    number_of_floors: int = 1


class ProjectUpdate(APIModel):
    name: str | None = None
    project_type: str | None = None
    year: int | None = None
    contractor: str | None = None
    engineer: str | None = None
    cpe: str | None = None
    checker: str | None = None
    facility: str | None = None
    facility_address: str | None = None
    project_description: str | None = None
    stage: str | None = None
    number_of_floors: int | None = None


class ProjectRead(APIModel):
    id: int
    name: str
    project_type: str
    number: int
    year: int
    code: str
    contractor: str
    engineer: str
    cpe: str
    checker: str
    facility: str
    facility_address: str | None = None
    project_description: str | None = None
    stage: str
    number_of_floors: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WallCreate(APIModel):
    floor_plan_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 200.0
    alignment: WallAlignment = "center"
    is_load_bearing: bool = False
    material: str | None = None
    length_m: float | None = None
    length_source: Literal["ocr", "manual", "derived"] | None = None


class WallUpdate(APIModel):
    floor_plan_id: int | None = None
    x1: float | None = None
    y1: float | None = None
    x2: float | None = None
    y2: float | None = None
    thickness: float | None = None
    alignment: WallAlignment | None = None
    is_load_bearing: bool | None = None
    material: str | None = None
    length_m: float | None = None
    length_source: Literal["ocr", "manual", "derived"] | None = None


class WallRead(APIModel):
    id: int
    floor_plan_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    alignment: WallAlignment = "center"
    is_load_bearing: bool
    material: str | None = None
    length_m: float | None = None
    length_source: str | None = None


class DoorCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    door_type: str = "standard"
    swing_angle: float = 90.0
    swing_direction: str | None = None


class DoorUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    wall_id: int | None = None
    rotation_deg: float | None = None
    door_type: str | None = None
    swing_angle: float | None = None
    swing_direction: str | None = None


class DoorRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    door_type: str
    swing_angle: float
    swing_direction: str | None = None


class WindowCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    window_type: str = "standard"


class WindowUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    wall_id: int | None = None
    rotation_deg: float | None = None
    window_type: str | None = None


class WindowRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    window_type: str


class RoomCreate(APIModel):
    floor_plan_id: int
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    boundary_points: list[list[float]] | None = None
    length_m: float | None = None
    width_m: float | None = None


class RoomUpdate(APIModel):
    floor_plan_id: int | None = None
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    boundary_points: list[list[float]] | None = None
    length_m: float | None = None
    width_m: float | None = None


class RoomRead(APIModel):
    id: int
    floor_plan_id: int
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    boundary_points: list[list[float]] | None = None
    area_sqm: float | None = None
    perimeter_m: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    center_x: float | None = None
    center_y: float | None = None


class DimensionCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    value: float
    unit: str = "m"
    text: str | None = None
    wall_id: int | None = None
    room_id: int | None = None
    line_x1: float | None = None
    line_y1: float | None = None
    line_x2: float | None = None
    line_y2: float | None = None
    dimension_type: str = "linear"


class DimensionRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    value: float
    unit: str
    text: str | None = None
    wall_id: int | None = None
    room_id: int | None = None
    line_x1: float | None = None
    line_y1: float | None = None
    line_x2: float | None = None
    line_y2: float | None = None
    dimension_type: str


class FireAlarmCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    device_type: str | None = None
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType | None = None
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmAutoLayoutDeviceRead(APIModel):
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmAutoLayoutRead(APIModel):
    devices: list[FireAlarmAutoLayoutDeviceRead] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class FloorPlanCreate(APIModel):
    project_id: int
    floor_number: int
    name: str | None = None
    scale_factor: float = 1.0
    ceiling_height_mm: float = 3000.0
    active_signal_system_type: SignalSystemType = "non_addressable"


class FloorPlanUpdate(APIModel):
    floor_number: int | None = None
    name: str | None = None
    scale_factor: float | None = None
    ceiling_height_mm: float | None = None
    active_signal_system_type: SignalSystemType | None = None


class StairCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float = 0.0
    step_count: int = 5
    step_axis: Literal["horizontal", "vertical"] | None = None


class StairUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    rotation_deg: float | None = None
    step_count: int | None = None
    step_axis: Literal["horizontal", "vertical"] | None = None


class StairRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float = 0.0
    step_count: int
    step_axis: Literal["horizontal", "vertical"]


class ZkspcZoneRead(APIModel):
    id: int
    floor_plan_id: int
    zone_number: int
    name: str | None = None
    area_sqm: float | None = None
    room_count: int
    room_ids: list[int] = Field(default_factory=list)
    is_manual: bool = False
    is_locked: bool = False
    compliance_warnings: list[str] = Field(default_factory=list)


class ZkspcZoneCommit(APIModel):
    id: int | None = None
    zone_number: int | None = None
    name: str | None = None
    room_ids: list[int] = Field(default_factory=list)
    is_manual: bool = True
    is_locked: bool = False


class SignalInstrumentCreate(APIModel):
    floor_plan_id: int
    system_type: SignalSystemType = "non_addressable"
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"] = "control_panel"
    x: float
    y: float
    name: str | None = None
    supports_cable_merge: bool | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SignalInstrumentUpdate(APIModel):
    floor_plan_id: int | None = None
    system_type: SignalSystemType | None = None
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"] | None = None
    x: float | None = None
    y: float | None = None
    name: str | None = None
    supports_cable_merge: bool | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SignalInstrumentRead(APIModel):
    id: int
    floor_plan_id: int
    system_type: SignalSystemType
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"]
    x: float
    y: float
    name: str | None = None
    supports_cable_merge: bool
    label_dx: float | None = None
    label_dy: float | None = None


class CableRouteRead(APIModel):
    id: int
    floor_plan_id: int
    system_type: SignalSystemType
    instrument_id: int
    route_kind: str
    route_number: int
    polyline_points: list[list[float]] = Field(default_factory=list)
    device_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    length_m: float | None = None
    is_manual: bool = False
    zc_label_dx: float | None = None
    zc_label_dy: float | None = None


class CableRouteUpdate(APIModel):
    polyline_points: list[list[float]] = Field(default_factory=list)
    is_manual: bool = True
    zc_label_dx: float | None = None
    zc_label_dy: float | None = None


class InstrumentCableMergeRequest(APIModel):
    device_ids: list[int] = Field(default_factory=list)


class CableRoutesRecalculateRequest(APIModel):
    system_type: SignalSystemType
    use_shared_trunk: bool = False


class FloorPlanRead(APIModel):
    id: int
    project_id: int
    floor_number: int
    name: str | None = None
    original_image_path: str | None = None
    processed_image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    scale_factor: float
    ceiling_height_mm: float = 3000.0
    active_signal_system_type: SignalSystemType = "non_addressable"
    pipeline_state: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    walls: list[WallRead] = Field(default_factory=list)
    stairs: list[StairRead] = Field(default_factory=list)
    doors: list[DoorRead] = Field(default_factory=list)
    windows: list[WindowRead] = Field(default_factory=list)
    rooms: list[RoomRead] = Field(default_factory=list)
    dimensions: list[DimensionRead] = Field(default_factory=list)
    fire_alarms: list[FireAlarmRead] = Field(default_factory=list)
    zkspc_zones: list[ZkspcZoneRead] = Field(default_factory=list)
    signal_instruments: list[SignalInstrumentRead] = Field(default_factory=list)
    cable_routes: list[CableRouteRead] = Field(default_factory=list)


class RecognitionProcessRead(APIModel):
    message: str
    walls_detected: int
    doors_detected: int
    windows_detected: int
    rooms_detected: int
    dimensions_detected: int
    recognition_id: int


class DebugImageRead(APIModel):
    step: str
    path: str


class RecognitionRead(APIModel):
    id: int | None = None
    floor_plan_id: int | None = None
    status: str
    recognition_result: dict[str, Any] | None = None
    error_message: str | None = None
    processed_at: datetime | None = None
    debug_artifacts_dir: str | None = None
    debug_images: list[DebugImageRead] = Field(default_factory=list)


class RecognitionFeedbackRead(APIModel):
    id: int
    recognition_id: int
    status: str
    submitted_at: datetime | None = None
    exported_at: datetime | None = None


class HealthRead(APIModel):
    status: str
    message: str


class MessageRead(APIModel):
    message: str


class FeedbackCreate(APIModel):
    objects: list[Any]


ElementType = Literal["walls", "stairs", "doors", "windows", "fire-alarms", "rooms", "dimensions"]


class DeleteElementCommand(APIModel):
    element_type: ElementType
    id: int


class WallUpdateCommand(APIModel):
    id: int
    data: WallUpdate


class DoorUpdateCommand(APIModel):
    id: int
    data: DoorUpdate


class WindowUpdateCommand(APIModel):
    id: int
    data: WindowUpdate


class StairUpdateCommand(APIModel):
    id: int
    data: StairUpdate


class FireAlarmUpdateCommand(APIModel):
    id: int
    data: FireAlarmUpdate


class RoomUpdateCommand(APIModel):
    id: int
    data: RoomUpdate


class BatchSaveRequest(APIModel):
    deleted: list[DeleteElementCommand] = Field(default_factory=list)
    create_walls: list[WallCreate] = Field(default_factory=list)
    create_stairs: list[StairCreate] = Field(default_factory=list)
    create_doors: list[DoorCreate] = Field(default_factory=list)
    create_windows: list[WindowCreate] = Field(default_factory=list)
    create_fire_alarms: list[FireAlarmCreate] = Field(default_factory=list)
    update_walls: list[WallUpdateCommand] = Field(default_factory=list)
    update_stairs: list[StairUpdateCommand] = Field(default_factory=list)
    update_doors: list[DoorUpdateCommand] = Field(default_factory=list)
    update_windows: list[WindowUpdateCommand] = Field(default_factory=list)
    update_rooms: list[RoomUpdateCommand] = Field(default_factory=list)
    update_fire_alarms: list[FireAlarmUpdateCommand] = Field(default_factory=list)


class BatchSaveResult(APIModel):
    message: str
    floor_plan: FloorPlanRead


StepStatus = Literal["draft", "validated", "stale", "locked"]


class PipelineStepState(APIModel):
    status: StepStatus = "draft"
    revision: int = 0
    detected_at: datetime | None = None
    committed_at: datetime | None = None


class PipelineBranchState(APIModel):
    active_step: str = "fire_alarms"
    steps: dict[str, PipelineStepState] = Field(default_factory=dict)


class PipelineStateRead(APIModel):
    floor_plan_id: int
    active_step: str = "walls"
    active_signal_system_type: SignalSystemType = "non_addressable"
    steps: dict[str, PipelineStepState]
    branches: dict[str, PipelineBranchState] = Field(default_factory=dict)


class WallLengthUpdate(APIModel):
    wall_id: int
    length_m: float
    length_source: Literal["ocr", "manual", "derived"] = "manual"


class PipelineWallsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)
    wall_lengths: list[WallLengthUpdate] = Field(default_factory=list)


class PipelineOpeningsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)


class RoomCommitUpdate(APIModel):
    room_id: int
    name: str | None = None
    room_number: str | None = None
    room_type: str | None = None
    length_m: float | None = None
    width_m: float | None = None


class PipelineRoomsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)
    room_updates: list[RoomCommitUpdate] = Field(default_factory=list)


class PipelineZkspcCommitRequest(APIModel):
    zones: list[ZkspcZoneCommit] = Field(default_factory=list)


class PipelineDetectResult(APIModel):
    message: str
    floor_plan: FloorPlanRead
    pipeline_state: PipelineStateRead


class PipelineCommitResult(APIModel):
    message: str
    floor_plan: FloorPlanRead
    pipeline_state: PipelineStateRead

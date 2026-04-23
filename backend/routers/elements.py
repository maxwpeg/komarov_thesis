"""Element routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.auth import (
    AuthenticatedUser,
    ensure_floor_plan_access,
    require_cable_route_access,
    require_current_user,
    require_dimension_access,
    require_door_access,
    require_fire_alarm_access,
    require_floor_plan_access,
    require_room_access,
    require_signal_instrument_access,
    require_soue_device_access,
    require_stair_access,
    require_wall_access,
    require_window_access,
)
from backend.background_jobs import (
    TASK_FIRE_ALARM_AUTO_LAYOUT,
    TASK_SOUE_AUTO_LAYOUT,
    dedupe_key_for_task,
)
from backend.database import get_db
from backend.dependencies import (
    get_elements_geometry_use_cases,
    get_floor_plan_use_cases,
    get_signal_design_use_cases,
)
from backend.fire_alarm_placement import calculate_fire_alarm_layout
from backend.mappers import (
    background_task_read,
    cable_route_read,
    dimension_read,
    door_read,
    fire_alarm_read,
    floor_plan_read,
    room_read,
    signal_instrument_read,
    soue_device_read,
    stair_read,
    wall_read,
    window_read,
    zkspc_zone_read,
)
from backend.modules.elements_geometry.application.use_cases import ElementsGeometryUseCases
from backend.modules.floor_plans.application.use_cases import FloorPlanUseCases
from backend.modules.signal_design.application.use_cases import SignalDesignUseCases
from backend.schemas import (
    BackgroundTaskRead,
    BatchSaveRequest,
    BatchSaveResult,
    CableRouteRead,
    CableRoutesRecalculateRequest,
    CableRouteUpdate,
    DimensionCreate,
    DimensionRead,
    DoorCreate,
    DoorRead,
    DoorUpdate,
    FireAlarmCreate,
    FireAlarmAutoLayoutRead,
    FireAlarmRead,
    FireAlarmUpdate,
    InstrumentCableMergeRequest,
    MessageRead,
    RoomCreate,
    RoomRead,
    RoomUpdate,
    SignalBranchStepCommitRequest,
    SignalInstrumentCreate,
    SignalInstrumentRead,
    SignalInstrumentUpdate,
    SoueDeviceAutoLayoutRead,
    SoueDeviceCreate,
    SoueDeviceRead,
    SoueDeviceUpdate,
    StairCreate,
    StairRead,
    StairUpdate,
    WallCreate,
    WallRead,
    WallUpdate,
    WindowCreate,
    WindowRead,
    WindowUpdate,
    ZkspcZoneRead,
)
from backend.services.background_task_service import BackgroundTaskService


router = APIRouter(tags=["elements"], dependencies=[Depends(require_current_user)])


def _require_floor_plan(db: Session, current_user: AuthenticatedUser, floor_plan_id: int) -> None:
    ensure_floor_plan_access(db, current_user, floor_plan_id)


@router.post("/api/walls", response_model=WallRead)
def create_wall(
    payload: WallCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WallRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return wall_read(service.create_wall(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/walls",
    response_model=list[WallRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_walls(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[WallRead]:
    return [wall_read(wall) for wall in service.list_walls(floor_plan_id)]


@router.patch("/api/walls/{wall_id}", response_model=WallRead, dependencies=[Depends(require_wall_access)])
def update_wall(
    wall_id: int,
    payload: WallUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WallRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return wall_read(service.update_wall(wall_id, payload))


@router.delete("/api/walls/{wall_id}", response_model=MessageRead, dependencies=[Depends(require_wall_access)])
def delete_wall(wall_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_wall(wall_id)
    return MessageRead(message="Wall deleted")


@router.post("/api/doors", response_model=DoorRead)
def create_door(
    payload: DoorCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> DoorRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return door_read(service.create_door(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/doors",
    response_model=list[DoorRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_doors(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[DoorRead]:
    return [door_read(door) for door in service.list_doors(floor_plan_id)]


@router.patch("/api/doors/{door_id}", response_model=DoorRead, dependencies=[Depends(require_door_access)])
def update_door(
    door_id: int,
    payload: DoorUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> DoorRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return door_read(service.update_door(door_id, payload))


@router.delete("/api/doors/{door_id}", response_model=MessageRead, dependencies=[Depends(require_door_access)])
def delete_door(door_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_door(door_id)
    return MessageRead(message="Door deleted")


@router.post("/api/windows", response_model=WindowRead)
def create_window(
    payload: WindowCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WindowRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return window_read(service.create_window(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/windows",
    response_model=list[WindowRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_windows(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[WindowRead]:
    return [window_read(window) for window in service.list_windows(floor_plan_id)]


@router.patch("/api/windows/{window_id}", response_model=WindowRead, dependencies=[Depends(require_window_access)])
def update_window(
    window_id: int,
    payload: WindowUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WindowRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return window_read(service.update_window(window_id, payload))


@router.delete("/api/windows/{window_id}", response_model=MessageRead, dependencies=[Depends(require_window_access)])
def delete_window(window_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_window(window_id)
    return MessageRead(message="Window deleted")


@router.post("/api/stairs", response_model=StairRead)
def create_stair(
    payload: StairCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> StairRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return stair_read(service.create_stair(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/stairs",
    response_model=list[StairRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_stairs(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[StairRead]:
    return [stair_read(stair) for stair in service.list_stairs(floor_plan_id)]


@router.patch("/api/stairs/{stair_id}", response_model=StairRead, dependencies=[Depends(require_stair_access)])
def update_stair(
    stair_id: int,
    payload: StairUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> StairRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return stair_read(service.update_stair(stair_id, payload))


@router.delete("/api/stairs/{stair_id}", response_model=MessageRead, dependencies=[Depends(require_stair_access)])
def delete_stair(stair_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_stair(stair_id)
    return MessageRead(message="Stair deleted")


@router.post("/api/rooms", response_model=RoomRead)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> RoomRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return room_read(service.create_room(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/rooms",
    response_model=list[RoomRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_rooms(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[RoomRead]:
    return [room_read(room) for room in service.list_rooms(floor_plan_id)]


@router.patch("/api/rooms/{room_id}", response_model=RoomRead, dependencies=[Depends(require_room_access)])
def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> RoomRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return room_read(service.update_room(room_id, payload))


@router.delete("/api/rooms/{room_id}", response_model=MessageRead, dependencies=[Depends(require_room_access)])
def delete_room(room_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_room(room_id)
    return MessageRead(message="Room deleted")


@router.post("/api/dimensions", response_model=DimensionRead)
def create_dimension(
    payload: DimensionCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> DimensionRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return dimension_read(service.create_dimension(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/dimensions",
    response_model=list[DimensionRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_dimensions(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[DimensionRead]:
    return [dimension_read(item) for item in service.list_dimensions(floor_plan_id)]


@router.delete("/api/dimensions/{dimension_id}", response_model=MessageRead, dependencies=[Depends(require_dimension_access)])
def delete_dimension(
    dimension_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_dimension(dimension_id)
    return MessageRead(message="Dimension deleted")


@router.post("/api/fire-alarms", response_model=FireAlarmRead)
def create_fire_alarm(
    payload: FireAlarmCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> FireAlarmRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return fire_alarm_read(service.create_fire_alarm(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/fire-alarms",
    response_model=list[FireAlarmRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_fire_alarms(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[FireAlarmRead]:
    return [fire_alarm_read(item) for item in service.list_fire_alarms(floor_plan_id)]


@router.post(
    "/api/floor-plans/{floor_plan_id}/fire-alarms/auto-layout",
    response_model=BackgroundTaskRead,
    status_code=202,
    dependencies=[Depends(require_floor_plan_access)],
)
def auto_layout_fire_alarms(
    floor_plan_id: int,
    system_type: str = Query("non_addressable"),
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_FIRE_ALARM_AUTO_LAYOUT,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id, "system_type": system_type},
        dedupe_key=dedupe_key_for_task(TASK_FIRE_ALARM_AUTO_LAYOUT, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.patch("/api/fire-alarms/{fire_alarm_id}", response_model=FireAlarmRead, dependencies=[Depends(require_fire_alarm_access)])
def update_fire_alarm(
    fire_alarm_id: int,
    payload: FireAlarmUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> FireAlarmRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return fire_alarm_read(service.update_fire_alarm(fire_alarm_id, payload))


@router.delete("/api/fire-alarms/{fire_alarm_id}", response_model=MessageRead, dependencies=[Depends(require_fire_alarm_access)])
def delete_fire_alarm(
    fire_alarm_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_fire_alarm(fire_alarm_id)
    return MessageRead(message="Fire alarm deleted")


@router.post("/api/soue-devices", response_model=SoueDeviceRead)
def create_soue_device(
    payload: SoueDeviceCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> SoueDeviceRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return soue_device_read(service.create_soue_device(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/soue-devices",
    response_model=list[SoueDeviceRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_soue_devices(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[SoueDeviceRead]:
    return [soue_device_read(item) for item in service.list_soue_devices(floor_plan_id)]


@router.post(
    "/api/floor-plans/{floor_plan_id}/soue-devices/auto-layout",
    response_model=BackgroundTaskRead,
    status_code=202,
    dependencies=[Depends(require_floor_plan_access)],
)
def auto_layout_soue_devices(
    floor_plan_id: int,
    system_type: str = Query("non_addressable"),
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_SOUE_AUTO_LAYOUT,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id, "system_type": system_type},
        dedupe_key=dedupe_key_for_task(TASK_SOUE_AUTO_LAYOUT, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.patch("/api/soue-devices/{soue_device_id}", response_model=SoueDeviceRead, dependencies=[Depends(require_soue_device_access)])
def update_soue_device(
    soue_device_id: int,
    payload: SoueDeviceUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> SoueDeviceRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return soue_device_read(service.update_soue_device(soue_device_id, payload))


@router.delete("/api/soue-devices/{soue_device_id}", response_model=MessageRead, dependencies=[Depends(require_soue_device_access)])
def delete_soue_device(
    soue_device_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_soue_device(soue_device_id)
    return MessageRead(message="SOUe device deleted")


@router.post(
    "/api/floor-plans/{floor_plan_id}/batch-save",
    response_model=BatchSaveResult,
    dependencies=[Depends(require_floor_plan_access)],
)
def batch_save_floor_plan(
    floor_plan_id: int,
    payload: BatchSaveRequest,
    element_service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
    floor_plan_service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> BatchSaveResult:
    element_service.batch_save(floor_plan_id, payload)
    floor_plan = floor_plan_service.get_floor_plan(floor_plan_id, include_elements=True)
    return BatchSaveResult(
        message="Changes saved successfully",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
    )


@router.post(
    "/api/floor-plans/{floor_plan_id}/calculate-fire-alarms",
    response_model=MessageRead,
    dependencies=[Depends(require_floor_plan_access)],
)
def calculate_fire_alarms(
    floor_plan_id: int,
    system_type: str = Query("non_addressable"),
    floor_plan_service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
    signal_service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    floor_plan = floor_plan_service.get_floor_plan(floor_plan_id, include_elements=True)
    layout = calculate_fire_alarm_layout(
        floor_plan.to_dict(include_elements=True),
        scale_factor=floor_plan.scale_factor,
        system_type=system_type,
        zkspc_zones=floor_plan.to_dict(include_elements=True).get("zkspc_zones", []),
    )
    payloads = [
        {
            "x": device["x"],
            "y": device["y"],
            "device_type": device["device_type"],
            "device_model": device.get("device_model"),
            "coverage_radius": device.get("coverage_radius"),
            "mounting_height": device.get("mounting_height"),
            "system_type": device.get("system_type"),
            "zkspc_zone_id": device.get("zkspc_zone_id"),
            "loop_kind": device.get("loop_kind"),
            "loop_number": device.get("loop_number"),
            "device_number": device.get("device_number"),
            "zone": device.get("zone"),
            "address": device.get("address"),
        }
        for device in layout["all_devices"]
    ]
    signal_service.replace_branch_fire_alarms(floor_plan_id, system_type, payloads)
    return MessageRead(message="Fire alarm devices calculated and placed successfully")


@router.get(
    "/api/floor-plans/{floor_plan_id}/zkspc-zones",
    response_model=list[ZkspcZoneRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_zkspc_zones(
    floor_plan_id: int,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[ZkspcZoneRead]:
    return [zkspc_zone_read(zone) for zone in service.list_zkspc_zones(floor_plan_id)]


@router.post("/api/signal-instruments", response_model=SignalInstrumentRead)
def create_signal_instrument(
    payload: SignalInstrumentCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> SignalInstrumentRead:
    _require_floor_plan(db, current_user, payload.floor_plan_id)
    return signal_instrument_read(service.create_signal_instrument(payload))


@router.get(
    "/api/floor-plans/{floor_plan_id}/signal-instruments",
    response_model=list[SignalInstrumentRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_signal_instruments(
    floor_plan_id: int,
    system_type: str | None = Query(None),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[SignalInstrumentRead]:
    return [signal_instrument_read(item) for item in service.list_signal_instruments(floor_plan_id, system_type)]


@router.patch(
    "/api/signal-instruments/{instrument_id}",
    response_model=SignalInstrumentRead,
    dependencies=[Depends(require_signal_instrument_access)],
)
def update_signal_instrument(
    instrument_id: int,
    payload: SignalInstrumentUpdate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> SignalInstrumentRead:
    if payload.floor_plan_id is not None:
        _require_floor_plan(db, current_user, payload.floor_plan_id)
    return signal_instrument_read(service.update_signal_instrument(instrument_id, payload))


@router.delete(
    "/api/signal-instruments/{instrument_id}",
    response_model=MessageRead,
    dependencies=[Depends(require_signal_instrument_access)],
)
def delete_signal_instrument(
    instrument_id: int,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.delete_signal_instrument(instrument_id)
    return MessageRead(message="Signal instrument deleted")


@router.post(
    "/api/floor-plans/{floor_plan_id}/signal-instruments/commit",
    response_model=MessageRead,
    dependencies=[Depends(require_floor_plan_access)],
)
def commit_signal_instruments_step(
    floor_plan_id: int,
    payload: SignalBranchStepCommitRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.commit_signal_instruments_step(floor_plan_id, payload.system_type)
    return MessageRead(message="Signal instruments step saved")


@router.post(
    "/api/signal-instruments/{instrument_id}/merge-routes",
    response_model=list[CableRouteRead],
    dependencies=[Depends(require_signal_instrument_access)],
)
def merge_routes_for_instrument(
    instrument_id: int,
    payload: InstrumentCableMergeRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[CableRouteRead]:
    return [
        cable_route_read(route)
        for route in service.merge_routes_for_instrument(
            instrument_id,
            payload.device_ids,
            payload.subsystem_type,
            payload.system_type,
        )
    ]


@router.get(
    "/api/floor-plans/{floor_plan_id}/cable-routes",
    response_model=list[CableRouteRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def list_cable_routes(
    floor_plan_id: int,
    system_type: str | None = Query(None),
    subsystem_type: str | None = Query(None),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[CableRouteRead]:
    return [cable_route_read(route) for route in service.list_cable_routes(floor_plan_id, system_type, subsystem_type)]


@router.post(
    "/api/floor-plans/{floor_plan_id}/cable-routes/recalculate",
    response_model=list[CableRouteRead],
    dependencies=[Depends(require_floor_plan_access)],
)
def recalculate_cable_routes_api(
    floor_plan_id: int,
    payload: CableRoutesRecalculateRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[CableRouteRead]:
    return [
        cable_route_read(route)
        for route in service.recalculate_routes(
            floor_plan_id,
            payload.system_type,
            payload.subsystem_type,
            payload.use_shared_trunk,
        )
    ]


@router.post(
    "/api/floor-plans/{floor_plan_id}/cable-routes/commit",
    response_model=MessageRead,
    dependencies=[Depends(require_floor_plan_access)],
)
def commit_cable_routes_step(
    floor_plan_id: int,
    payload: CableRoutesRecalculateRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.commit_routes_step(floor_plan_id, payload.system_type, payload.subsystem_type)
    return MessageRead(message="Cable routes step saved")


@router.patch("/api/cable-routes/{route_id}", response_model=CableRouteRead, dependencies=[Depends(require_cable_route_access)])
def update_cable_route(
    route_id: int,
    payload: CableRouteUpdate,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> CableRouteRead:
    return cable_route_read(service.update_cable_route(route_id, payload))

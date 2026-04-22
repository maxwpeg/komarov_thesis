"""Element routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.dependencies import (
    get_elements_geometry_use_cases,
    get_floor_plan_use_cases,
    get_signal_design_use_cases,
)
from backend.fire_alarm_placement import calculate_fire_alarm_layout
from backend.mappers import (
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


router = APIRouter(tags=["elements"])


@router.post("/api/walls", response_model=WallRead)
def create_wall(payload: WallCreate, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> WallRead:
    return wall_read(service.create_wall(payload))


@router.get("/api/floor-plans/{floor_plan_id}/walls", response_model=list[WallRead])
def list_walls(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[WallRead]:
    return [wall_read(wall) for wall in service.list_walls(floor_plan_id)]


@router.patch("/api/walls/{wall_id}", response_model=WallRead)
def update_wall(
    wall_id: int,
    payload: WallUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WallRead:
    return wall_read(service.update_wall(wall_id, payload))


@router.delete("/api/walls/{wall_id}", response_model=MessageRead)
def delete_wall(wall_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_wall(wall_id)
    return MessageRead(message="Wall deleted")


@router.post("/api/doors", response_model=DoorRead)
def create_door(payload: DoorCreate, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> DoorRead:
    return door_read(service.create_door(payload))


@router.get("/api/floor-plans/{floor_plan_id}/doors", response_model=list[DoorRead])
def list_doors(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[DoorRead]:
    return [door_read(door) for door in service.list_doors(floor_plan_id)]


@router.patch("/api/doors/{door_id}", response_model=DoorRead)
def update_door(
    door_id: int,
    payload: DoorUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> DoorRead:
    return door_read(service.update_door(door_id, payload))


@router.delete("/api/doors/{door_id}", response_model=MessageRead)
def delete_door(door_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_door(door_id)
    return MessageRead(message="Door deleted")


@router.post("/api/windows", response_model=WindowRead)
def create_window(payload: WindowCreate, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> WindowRead:
    return window_read(service.create_window(payload))


@router.get("/api/floor-plans/{floor_plan_id}/windows", response_model=list[WindowRead])
def list_windows(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[WindowRead]:
    return [window_read(window) for window in service.list_windows(floor_plan_id)]


@router.patch("/api/windows/{window_id}", response_model=WindowRead)
def update_window(
    window_id: int,
    payload: WindowUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> WindowRead:
    return window_read(service.update_window(window_id, payload))


@router.delete("/api/windows/{window_id}", response_model=MessageRead)
def delete_window(window_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_window(window_id)
    return MessageRead(message="Window deleted")


@router.post("/api/stairs", response_model=StairRead)
def create_stair(payload: StairCreate, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> StairRead:
    return stair_read(service.create_stair(payload))


@router.get("/api/floor-plans/{floor_plan_id}/stairs", response_model=list[StairRead])
def list_stairs(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[StairRead]:
    return [stair_read(stair) for stair in service.list_stairs(floor_plan_id)]


@router.patch("/api/stairs/{stair_id}", response_model=StairRead)
def update_stair(
    stair_id: int,
    payload: StairUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> StairRead:
    return stair_read(service.update_stair(stair_id, payload))


@router.delete("/api/stairs/{stair_id}", response_model=MessageRead)
def delete_stair(stair_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_stair(stair_id)
    return MessageRead(message="Stair deleted")


@router.post("/api/rooms", response_model=RoomRead)
def create_room(payload: RoomCreate, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> RoomRead:
    return room_read(service.create_room(payload))


@router.get("/api/floor-plans/{floor_plan_id}/rooms", response_model=list[RoomRead])
def list_rooms(floor_plan_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> list[RoomRead]:
    return [room_read(room) for room in service.list_rooms(floor_plan_id)]


@router.patch("/api/rooms/{room_id}", response_model=RoomRead)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> RoomRead:
    return room_read(service.update_room(room_id, payload))


@router.delete("/api/rooms/{room_id}", response_model=MessageRead)
def delete_room(room_id: int, service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases)) -> MessageRead:
    service.delete_room(room_id)
    return MessageRead(message="Room deleted")


@router.post("/api/dimensions", response_model=DimensionRead)
def create_dimension(
    payload: DimensionCreate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> DimensionRead:
    return dimension_read(service.create_dimension(payload))


@router.get("/api/floor-plans/{floor_plan_id}/dimensions", response_model=list[DimensionRead])
def list_dimensions(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[DimensionRead]:
    return [dimension_read(item) for item in service.list_dimensions(floor_plan_id)]


@router.delete("/api/dimensions/{dimension_id}", response_model=MessageRead)
def delete_dimension(
    dimension_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_dimension(dimension_id)
    return MessageRead(message="Dimension deleted")


@router.post("/api/fire-alarms", response_model=FireAlarmRead)
def create_fire_alarm(
    payload: FireAlarmCreate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> FireAlarmRead:
    return fire_alarm_read(service.create_fire_alarm(payload))


@router.get("/api/floor-plans/{floor_plan_id}/fire-alarms", response_model=list[FireAlarmRead])
def list_fire_alarms(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[FireAlarmRead]:
    return [fire_alarm_read(item) for item in service.list_fire_alarms(floor_plan_id)]


@router.post(
    "/api/floor-plans/{floor_plan_id}/fire-alarms/auto-layout",
    response_model=FireAlarmAutoLayoutRead,
)
def auto_layout_fire_alarms(
    floor_plan_id: int,
    system_type: str = Query("non_addressable"),
    signal_service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> FireAlarmAutoLayoutRead:
    layout = signal_service.auto_layout_fire_alarms(floor_plan_id, system_type)
    return FireAlarmAutoLayoutRead(
        devices=layout["all_devices"],
        summary=layout["summary"],
        warnings=layout.get("warnings", []),
    )


@router.patch("/api/fire-alarms/{fire_alarm_id}", response_model=FireAlarmRead)
def update_fire_alarm(
    fire_alarm_id: int,
    payload: FireAlarmUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> FireAlarmRead:
    return fire_alarm_read(service.update_fire_alarm(fire_alarm_id, payload))


@router.delete("/api/fire-alarms/{fire_alarm_id}", response_model=MessageRead)
def delete_fire_alarm(
    fire_alarm_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_fire_alarm(fire_alarm_id)
    return MessageRead(message="Fire alarm deleted")


@router.post("/api/soue-devices", response_model=SoueDeviceRead)
def create_soue_device(
    payload: SoueDeviceCreate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> SoueDeviceRead:
    return soue_device_read(service.create_soue_device(payload))


@router.get("/api/floor-plans/{floor_plan_id}/soue-devices", response_model=list[SoueDeviceRead])
def list_soue_devices(
    floor_plan_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> list[SoueDeviceRead]:
    return [soue_device_read(item) for item in service.list_soue_devices(floor_plan_id)]


@router.post(
    "/api/floor-plans/{floor_plan_id}/soue-devices/auto-layout",
    response_model=SoueDeviceAutoLayoutRead,
)
def auto_layout_soue_devices(
    floor_plan_id: int,
    system_type: str = Query("non_addressable"),
    signal_service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> SoueDeviceAutoLayoutRead:
    layout = signal_service.auto_layout_soue_devices(floor_plan_id, system_type)
    return SoueDeviceAutoLayoutRead(
        devices=layout["devices"],
        summary=layout["summary"],
        warnings=layout.get("warnings", []),
    )


@router.patch("/api/soue-devices/{soue_device_id}", response_model=SoueDeviceRead)
def update_soue_device(
    soue_device_id: int,
    payload: SoueDeviceUpdate,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> SoueDeviceRead:
    return soue_device_read(service.update_soue_device(soue_device_id, payload))


@router.delete("/api/soue-devices/{soue_device_id}", response_model=MessageRead)
def delete_soue_device(
    soue_device_id: int,
    service: ElementsGeometryUseCases = Depends(get_elements_geometry_use_cases),
) -> MessageRead:
    service.delete_soue_device(soue_device_id)
    return MessageRead(message="SOUe device deleted")


@router.post("/api/floor-plans/{floor_plan_id}/batch-save", response_model=BatchSaveResult)
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


@router.post("/api/floor-plans/{floor_plan_id}/calculate-fire-alarms", response_model=MessageRead)
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


@router.get("/api/floor-plans/{floor_plan_id}/zkspc-zones", response_model=list[ZkspcZoneRead])
def list_zkspc_zones(
    floor_plan_id: int,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[ZkspcZoneRead]:
    return [zkspc_zone_read(zone) for zone in service.list_zkspc_zones(floor_plan_id)]


@router.post("/api/signal-instruments", response_model=SignalInstrumentRead)
def create_signal_instrument(
    payload: SignalInstrumentCreate,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> SignalInstrumentRead:
    return signal_instrument_read(service.create_signal_instrument(payload))


@router.get("/api/floor-plans/{floor_plan_id}/signal-instruments", response_model=list[SignalInstrumentRead])
def list_signal_instruments(
    floor_plan_id: int,
    system_type: str | None = Query(None),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[SignalInstrumentRead]:
    return [signal_instrument_read(item) for item in service.list_signal_instruments(floor_plan_id, system_type)]


@router.patch("/api/signal-instruments/{instrument_id}", response_model=SignalInstrumentRead)
def update_signal_instrument(
    instrument_id: int,
    payload: SignalInstrumentUpdate,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> SignalInstrumentRead:
    return signal_instrument_read(service.update_signal_instrument(instrument_id, payload))


@router.delete("/api/signal-instruments/{instrument_id}", response_model=MessageRead)
def delete_signal_instrument(
    instrument_id: int,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.delete_signal_instrument(instrument_id)
    return MessageRead(message="Signal instrument deleted")


@router.post("/api/floor-plans/{floor_plan_id}/signal-instruments/commit", response_model=MessageRead)
def commit_signal_instruments_step(
    floor_plan_id: int,
    payload: SignalBranchStepCommitRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.commit_signal_instruments_step(floor_plan_id, payload.system_type)
    return MessageRead(message="Signal instruments step saved")


@router.post("/api/signal-instruments/{instrument_id}/merge-routes", response_model=list[CableRouteRead])
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


@router.get("/api/floor-plans/{floor_plan_id}/cable-routes", response_model=list[CableRouteRead])
def list_cable_routes(
    floor_plan_id: int,
    system_type: str | None = Query(None),
    subsystem_type: str | None = Query(None),
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> list[CableRouteRead]:
    return [cable_route_read(route) for route in service.list_cable_routes(floor_plan_id, system_type, subsystem_type)]


@router.post("/api/floor-plans/{floor_plan_id}/cable-routes/recalculate", response_model=list[CableRouteRead])
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


@router.post("/api/floor-plans/{floor_plan_id}/cable-routes/commit", response_model=MessageRead)
def commit_cable_routes_step(
    floor_plan_id: int,
    payload: CableRoutesRecalculateRequest,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> MessageRead:
    service.commit_routes_step(floor_plan_id, payload.system_type, payload.subsystem_type)
    return MessageRead(message="Cable routes step saved")


@router.patch("/api/cable-routes/{route_id}", response_model=CableRouteRead)
def update_cable_route(
    route_id: int,
    payload: CableRouteUpdate,
    service: SignalDesignUseCases = Depends(get_signal_design_use_cases),
) -> CableRouteRead:
    return cable_route_read(service.update_cable_route(route_id, payload))

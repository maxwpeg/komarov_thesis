"""Step-by-step floor plan pipeline orchestration service."""

from __future__ import annotations

import math
from typing import Iterable

import cv2
import numpy as np
from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.models import (
    Dimension as DimensionModel,
    Door as DoorModel,
    FloorPlan as FloorPlanModel,
    Room as RoomModel,
    Wall as WallModel,
    Window as WindowModel,
)
from backend.modules.pipeline.domain.state import (
    BRANCH_STEPS,
    PIPELINE_STEPS,
    SIGNAL_BRANCHES,
    PipelineStateModel,
)
from backend.modules.pipeline.application.state_manager import PipelineStateManager
from backend.schemas import (
    PipelineOpeningsCommitRequest,
    PipelineRoomsCommitRequest,
    PipelineStateRead,
    PipelineWallsCommitRequest,
    PipelineZkspcCommitRequest,
)
from backend.modules.pipeline.application.errors import WallValidationError
from backend.services.element_service import ElementService
from backend.services.signal_service import SignalService
from backend.services.storage_service import StorageService
from floorplan.floorplan_types import (
    Dimension as DetectedDimension,
    LineSegment,
    Room as DetectedRoom,
    Wall as DetectedWall,
)
from floorplan.ocr_dimensions import assign_dimensions, detect_text_dimensions
from floorplan.openings import classify_opening, find_gaps_along_wall, remove_duplicate_openings
from floorplan.preprocess import preprocess
from floorplan.rooms import detect_rooms
from floorplan.walls_morph import detect_walls


class PipelineService:
    """Orchestrates step detection and commit operations."""

    def __init__(self, db: Session, storage: StorageService):
        self.db = db
        self.storage = storage
        self.element_service = ElementService(db)
        self.signal_service = SignalService(db)
        self.state_manager = PipelineStateManager()

    def get_pipeline_state(self, floor_plan_id: int) -> PipelineStateRead:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        return self._state_read(floor_plan.id, state)

    def detect_walls(self, floor_plan_id: int) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        binary, preprocessed = self._load_preprocessed_images(floor_plan)
        state = self._load_pipeline_state(floor_plan)

        existing_walls = (
            self.db.query(WallModel)
            .filter(WallModel.floor_plan_id == floor_plan_id)
            .all()
        )
        existing_manual_lengths = [
            wall for wall in existing_walls if wall.length_m and wall.length_source in {"manual", "ocr"}
        ]

        detected_walls = detect_walls(binary)
        detected_dimensions = assign_dimensions(detect_text_dimensions(preprocessed), detected_walls, [])
        self.db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).delete()
        self.db.query(DimensionModel).filter(DimensionModel.floor_plan_id == floor_plan_id).delete()

        scale_factor = floor_plan.scale_factor or 1.0
        new_wall_models: list[WallModel] = []
        for wall in detected_walls:
            pixel_length = math.hypot(wall.midline.x2 - wall.midline.x1, wall.midline.y2 - wall.midline.y1)
            length_m = pixel_length * scale_factor / 1000.0
            length_source = "derived"

            preserved = self._find_matching_existing_wall(wall, existing_manual_lengths)
            if preserved is not None and preserved.length_m:
                length_m = float(preserved.length_m)
                length_source = preserved.length_source or "manual"

            db_wall = WallModel(
                floor_plan_id=floor_plan_id,
                x1=float(wall.midline.x1),
                y1=float(wall.midline.y1),
                x2=float(wall.midline.x2),
                y2=float(wall.midline.y2),
                thickness=float(wall.thickness_px * scale_factor),
                alignment="center",
                is_load_bearing=False,
                material=f"detected_wall_{wall.id}",
                length_m=length_m,
                length_source=length_source,
            )
            self.db.add(db_wall)
            new_wall_models.append(db_wall)

        self.db.flush()
        wall_id_map = self._build_wall_id_map(new_wall_models)

        for dim in detected_dimensions:
            db_dim = DimensionModel(
                floor_plan_id=floor_plan_id,
                x=float(dim.x),
                y=float(dim.y),
                value=float(dim.value),
                unit=dim.unit or "m",
                text=dim.text,
                wall_id=wall_id_map.get(int(dim.wall_id)) if dim.wall_id is not None else None,
                room_id=None,
                line_x1=dim.line_x1,
                line_y1=dim.line_y1,
                line_x2=dim.line_x2,
                line_y2=dim.line_y2,
                dimension_type="linear",
            )
            self.db.add(db_dim)

        self.element_service.relink_or_prune_openings(floor_plan_id, delete_invalid=True)

        self._set_step_status(state, "walls", "draft", detected=True)
        self._mark_downstream_stale(state, "walls")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def commit_walls(
        self,
        floor_plan_id: int,
        payload: PipelineWallsCommitRequest,
    ) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)

        if payload.changes:
            self.element_service.batch_save(floor_plan_id, payload.changes, commit=False)

        for update in payload.wall_lengths:
            wall = self._get_wall(floor_plan_id, update.wall_id)
            wall.length_m = float(update.length_m)
            wall.length_source = update.length_source

        walls = (
            self.db.query(WallModel)
            .filter(WallModel.floor_plan_id == floor_plan_id)
            .all()
        )
        missing_wall_ids = [wall.id for wall in walls if wall.length_m is None or wall.length_m <= 0]
        if missing_wall_ids:
            self.db.rollback()
            raise WallValidationError(sorted(missing_wall_ids))

        if (floor_plan.scale_source or "auto") == "manual" and (floor_plan.scale_factor or 0) > 0:
            recalculated_scale = float(floor_plan.scale_factor)
        else:
            recalculated_scale = self._recalculate_scale_factor(walls, floor_plan.scale_factor or 1.0)
            floor_plan.scale_factor = recalculated_scale
            floor_plan.scale_source = "auto"

        for wall in walls:
            pixel_length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
            if pixel_length < 1e-6:
                continue
            if wall.length_source in {None, "derived"}:
                wall.length_m = pixel_length * recalculated_scale / 1000.0
                wall.length_source = "derived"

        rooms = self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
        for room in rooms:
            room.calculate_center()
            room.calculate_length_width(recalculated_scale)
            room.calculate_area(recalculated_scale)
            room.calculate_perimeter(recalculated_scale)

        self.element_service.relink_or_prune_openings(floor_plan_id, delete_invalid=True)

        self._set_step_status(state, "walls", "validated", committed=True, bump_revision=True)
        self._mark_downstream_stale(state, "walls")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def detect_openings(self, floor_plan_id: int) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "walls", "Walls must be validated before openings detection")

        binary, preprocessed = self._load_preprocessed_images(floor_plan)
        walls = self._load_detected_walls_from_db(floor_plan)
        all_gaps = []
        for wall in walls:
            all_gaps.extend(find_gaps_along_wall(wall, binary))

        openings = []
        for gap in all_gaps:
            wall = next((item for item in walls if item.id == gap.wall_id), None)
            if wall is None:
                continue
            classified = classify_opening(gap, wall, binary, preprocessed)
            if classified is None:
                continue
            opening_type, confidence, metadata = classified
            x1, y1, x2, y2 = gap.bbox
            openings.append(
                {
                    "type": opening_type.value,
                    "wall_id": wall.id,
                    "bbox": (x1, y1, x2, y2),
                    "confidence": float(confidence),
                }
            )
        openings = remove_duplicate_openings(
            [
                # lightweight adapter object expected by remove_duplicate_openings
                type(
                    "OpeningAdapter",
                    (),
                    {
                        "type": type("OpeningTypeAdapter", (), {"value": item["type"]})(),
                        "wall_id": item["wall_id"],
                        "bbox": item["bbox"],
                        "confidence": item["confidence"],
                    },
                )()
                for item in openings
            ]
        )

        self.db.query(DoorModel).filter(DoorModel.floor_plan_id == floor_plan_id).delete()
        self.db.query(WindowModel).filter(WindowModel.floor_plan_id == floor_plan_id).delete()

        for opening in openings:
            x1, y1, x2, y2 = opening.bbox
            data = dict(
                floor_plan_id=floor_plan_id,
                x=float(x1),
                y=float(y1),
                width=float(max(1, x2 - x1)),
                height=float(max(1, y2 - y1)),
                wall_id=int(opening.wall_id) if opening.wall_id is not None else None,
            )
            if opening.type.value == "door":
                self.db.add(
                    DoorModel(
                        **data,
                        door_type="standard",
                        swing_angle=90.0,
                        swing_direction=None,
                    )
                )
            else:
                self.db.add(
                    WindowModel(
                        **data,
                        window_type="standard",
                    )
                )

        self._set_step_status(state, "openings", "draft", detected=True)
        self._mark_downstream_stale(state, "openings")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def commit_openings(
        self,
        floor_plan_id: int,
        payload: PipelineOpeningsCommitRequest,
    ) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "walls", "Walls must be validated before openings commit")

        if payload.changes:
            self.element_service.batch_save(floor_plan_id, payload.changes, commit=False)
        else:
            self.element_service._normalize_floor_plan_openings(floor_plan_id)  # pylint: disable=protected-access

        self._set_step_status(state, "openings", "validated", committed=True, bump_revision=True)
        self._mark_downstream_stale(state, "openings")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def detect_rooms(self, floor_plan_id: int) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "walls", "Walls must be validated before room detection")
        self._ensure_step_validated(state, "openings", "Openings must be validated before room detection")

        binary, _preprocessed = self._load_preprocessed_images(floor_plan)
        walls = self._load_detected_walls_from_db(floor_plan)
        detected_rooms = detect_rooms(binary, walls)

        existing_rooms = self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
        self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).delete()

        for room in detected_rooms:
            db_room = RoomModel(
                floor_plan_id=floor_plan_id,
                name=room.name,
                room_type="базовое",
                room_number=room.room_number,
                boundary_points=room.boundary_points,
            )
            preserved_name = self._match_room_name(room, existing_rooms)
            if preserved_name:
                db_room.name = preserved_name
            db_room.calculate_center()
            db_room.calculate_length_width(floor_plan.scale_factor or 1.0)
            db_room.calculate_area(floor_plan.scale_factor or 1.0)
            db_room.calculate_perimeter(floor_plan.scale_factor or 1.0)
            self.db.add(db_room)

        self._set_step_status(state, "rooms", "draft", detected=True)
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def commit_rooms(
        self,
        floor_plan_id: int,
        payload: PipelineRoomsCommitRequest,
    ) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "walls", "Walls must be validated before room commit")
        self._ensure_step_validated(state, "openings", "Openings must be validated before room commit")

        if payload.changes:
            self.element_service.batch_save(floor_plan_id, payload.changes, commit=False)

        for room_update in payload.room_updates:
            room = self._get_room(floor_plan_id, room_update.room_id)
            if room_update.name is not None:
                room.name = room_update.name
            if room_update.room_number is not None:
                room.room_number = room_update.room_number
            if room_update.room_type is not None:
                room.room_type = room_update.room_type

        rooms = self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
        for room in rooms:
            room.calculate_center()
            room.calculate_length_width(floor_plan.scale_factor or 1.0)
            room.calculate_area(floor_plan.scale_factor or 1.0)
            room.calculate_perimeter(floor_plan.scale_factor or 1.0)

        self._set_step_status(state, "rooms", "validated", committed=True, bump_revision=True)
        self._mark_downstream_stale(state, "rooms")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def detect_zkspc(self, floor_plan_id: int) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "rooms", "Rooms must be validated before ZKSPC detection")
        self.signal_service.detect_zkspc(floor_plan_id)
        self._set_step_status(state, "zkspc", "draft", detected=True)
        self._reset_branch_steps(state, status="locked")
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def commit_zkspc(
        self,
        floor_plan_id: int,
        payload: PipelineZkspcCommitRequest,
    ) -> tuple[FloorPlanModel, PipelineStateRead]:
        floor_plan = self._get_floor_plan(floor_plan_id)
        state = self._load_pipeline_state(floor_plan)
        self._ensure_step_validated(state, "rooms", "Rooms must be validated before ZKSPC commit")
        self.signal_service.replace_zkspc_zones(floor_plan_id, payload.zones)
        self._set_step_status(state, "zkspc", "validated", committed=True, bump_revision=True)
        self._activate_branch_steps(state)
        state = self._store_pipeline_state(floor_plan, state)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan, self._state_read(floor_plan.id, state)

    def _get_floor_plan(self, floor_plan_id: int) -> FloorPlanModel:
        floor_plan = self.db.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    def _get_wall(self, floor_plan_id: int, wall_id: int) -> WallModel:
        wall = (
            self.db.query(WallModel)
            .filter(WallModel.id == wall_id, WallModel.floor_plan_id == floor_plan_id)
            .first()
        )
        if wall is None:
            raise AppError(404, "wall_not_found", "Wall not found")
        return wall

    def _get_room(self, floor_plan_id: int, room_id: int) -> RoomModel:
        room = (
            self.db.query(RoomModel)
            .filter(RoomModel.id == room_id, RoomModel.floor_plan_id == floor_plan_id)
            .first()
        )
        if room is None:
            raise AppError(404, "room_not_found", "Room not found")
        return room

    def _load_preprocessed_images(self, floor_plan: FloorPlanModel) -> tuple[np.ndarray, np.ndarray]:
        image_path = self.storage.absolute_path(floor_plan.original_image_path)
        if image_path is None or not image_path.exists():
            raise AppError(400, "floor_plan_image_missing", "Floor plan image not found")
        return preprocess(str(image_path), rectify=True, deskew_enabled=False)

    def _load_detected_walls_from_db(self, floor_plan: FloorPlanModel) -> list[DetectedWall]:
        walls = self.db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan.id).all()
        scale_factor = floor_plan.scale_factor or 1.0
        detected: list[DetectedWall] = []
        for wall in walls:
            dx = wall.x2 - wall.x1
            dy = wall.y2 - wall.y1
            angle = math.degrees(math.atan2(dy, dx)) % 180.0
            detected.append(
                DetectedWall(
                    id=wall.id,
                    midline=LineSegment(
                        x1=float(wall.x1),
                        y1=float(wall.y1),
                        x2=float(wall.x2),
                        y2=float(wall.y2),
                        length=float(math.hypot(dx, dy)),
                        angle=angle,
                    ),
                    thickness_px=float((wall.thickness or 1.0) / scale_factor),
                    angle_deg=float(angle),
                    confidence=1.0,
                )
            )
        return detected

    @staticmethod
    def _build_wall_id_map(walls: Iterable[WallModel]) -> dict[int, int]:
        mapping: dict[int, int] = {}
        for wall in walls:
            material = wall.material or ""
            if material.startswith("detected_wall_"):
                suffix = material.replace("detected_wall_", "", 1)
                try:
                    mapping[int(suffix)] = wall.id
                except ValueError:
                    continue
        return mapping

    @staticmethod
    def _recalculate_scale_factor(walls: list[WallModel], current_scale: float) -> float:
        ratios: list[float] = []
        weights: list[float] = []
        for wall in walls:
            if wall.length_m is None or wall.length_m <= 0:
                continue
            pixel_length = math.hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
            if pixel_length <= 1e-6:
                continue
            ratios.append((wall.length_m * 1000.0) / pixel_length)
            weights.append(max(1.0, pixel_length))

        if not ratios:
            return current_scale

        pairs = sorted(zip(ratios, weights), key=lambda item: item[0])
        total_weight = sum(weights)
        cumulative = 0.0
        for value, weight in pairs:
            cumulative += weight
            if cumulative >= total_weight / 2.0:
                return float(value)
        return float(pairs[-1][0])

    def _load_pipeline_state(self, floor_plan: FloorPlanModel) -> dict:
        return self.state_manager.load(floor_plan.pipeline_state, floor_plan.active_signal_system_type)

    def _store_pipeline_state(self, floor_plan: FloorPlanModel, state: dict) -> dict:
        return self.state_manager.store(floor_plan, state)

    def _state_read(self, floor_plan_id: int, state: dict) -> PipelineStateRead:
        return self.state_manager.read(floor_plan_id, state)

    def _set_step_status(
        self,
        state: dict,
        step_name: str,
        status: str,
        *,
        detected: bool = False,
        committed: bool = False,
        bump_revision: bool = False,
    ) -> None:
        updated = self.state_manager.set_step_status(
            state,
            step_name,
            status,
            detected=detected,
            committed=committed,
            bump_revision=bump_revision,
        )
        state.clear()
        state.update(updated)

    def _mark_downstream_stale(self, state: dict, from_step: str) -> None:
        updated = self.state_manager.mark_downstream_stale(state, from_step)
        state.clear()
        state.update(updated)

    def _reset_branch_steps(self, state: dict, status: str = "locked") -> None:
        updated = self.state_manager.reset_branch_steps(state, status=status)
        state.clear()
        state.update(updated)

    def _activate_branch_steps(self, state: dict) -> None:
        updated = self.state_manager.activate_branch_steps(state)
        state.clear()
        state.update(updated)

    def _ensure_step_validated(self, state: dict, step_name: str, error_detail: str) -> None:
        self.state_manager.ensure_step_validated(state, step_name, error_detail)

    @staticmethod
    def _find_matching_existing_wall(
        wall: DetectedWall,
        existing_walls: list[WallModel],
    ) -> WallModel | None:
        if not existing_walls:
            return None

        x1, y1 = wall.midline.x1, wall.midline.y1
        x2, y2 = wall.midline.x2, wall.midline.y2
        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        length = math.hypot(x2 - x1, y2 - y1)

        best_wall = None
        best_score = float("inf")
        for existing in existing_walls:
            ex_dx = existing.x2 - existing.x1
            ex_dy = existing.y2 - existing.y1
            ex_length = math.hypot(ex_dx, ex_dy)
            if ex_length < 1e-6:
                continue
            ex_angle = math.degrees(math.atan2(ex_dy, ex_dx)) % 180.0
            angle_diff = min(abs(angle - ex_angle), 180.0 - abs(angle - ex_angle))
            if angle_diff > 12.0:
                continue

            ex_mid_x = (existing.x1 + existing.x2) / 2.0
            ex_mid_y = (existing.y1 + existing.y2) / 2.0
            midpoint_dist = math.hypot(mid_x - ex_mid_x, mid_y - ex_mid_y)
            length_ratio = abs(length - ex_length) / max(1.0, length, ex_length)
            score = midpoint_dist + length_ratio * 100.0
            if score < best_score:
                best_score = score
                best_wall = existing

        if best_score > 80.0:
            return None
        return best_wall

    @staticmethod
    def _match_room_name(room: DetectedRoom, existing_rooms: list[RoomModel]) -> str | None:
        if not room.boundary_points:
            return None
        target = np.array(room.boundary_points, dtype=np.float32)
        if len(target) < 3:
            return None

        best_name = None
        best_iou = 0.0
        for old_room in existing_rooms:
            if not old_room.name or not old_room.boundary_points or len(old_room.boundary_points) < 3:
                continue
            old = np.array(old_room.boundary_points, dtype=np.float32)
            iou = PipelineService._polygon_iou(target, old)
            if iou > best_iou:
                best_iou = iou
                best_name = old_room.name
        if best_iou >= 0.5:
            return best_name
        return None

    @staticmethod
    def _polygon_iou(poly1: np.ndarray, poly2: np.ndarray) -> float:
        min_x = int(np.floor(min(poly1[:, 0].min(), poly2[:, 0].min()))) - 2
        min_y = int(np.floor(min(poly1[:, 1].min(), poly2[:, 1].min()))) - 2
        max_x = int(np.ceil(max(poly1[:, 0].max(), poly2[:, 0].max()))) + 2
        max_y = int(np.ceil(max(poly1[:, 1].max(), poly2[:, 1].max()))) + 2
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        if width <= 2 or height <= 2:
            return 0.0

        shifted1 = (poly1 - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32).reshape((-1, 1, 2))
        shifted2 = (poly2 - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32).reshape((-1, 1, 2))

        mask1 = np.zeros((height, width), dtype=np.uint8)
        mask2 = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask1, [shifted1], 255)
        cv2.fillPoly(mask2, [shifted2], 255)

        intersection = np.logical_and(mask1 > 0, mask2 > 0).sum()
        union = np.logical_or(mask1 > 0, mask2 > 0).sum()
        if union == 0:
            return 0.0
        return float(intersection) / float(union)

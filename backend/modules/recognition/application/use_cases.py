"""Explicit application use cases for recognition."""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import cv2
import numpy as np

from backend.config import settings
from backend.errors import AppError
from backend.modules.recognition.ports.repositories import RecognitionRepository
from backend.modules.recognition.domain.records import RecognitionRecord
from backend.modules.recognition.infrastructure.adapter import FloorplanRecognitionAdapter
from backend.modules.shared.application.ports import FileStoragePort
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher
from backend.schemas import RecognitionFeedbackRead, RecognitionRead


logger = logging.getLogger("komarov_thesis")


@dataclass(slots=True)
class RecognitionUseCases:
    """Recognition orchestration use cases."""

    repository: RecognitionRepository
    storage: FileStoragePort
    uow: UnitOfWork
    events: Any | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = NoOpEventPublisher()

    def process_floor_plan(self, floor_plan_id: int, debug: bool = False) -> tuple[int, int, int, int, int, int]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        image_path = self.storage.absolute_path(floor_plan.original_image_path)
        if image_path is None or not image_path.exists():
            raise AppError(400, "floor_plan_image_missing", "Floor plan image not found")

        debug_dir = self.storage.debug_dir(floor_plan_id) if debug else None
        adapter = FloorplanRecognitionAdapter(debug=debug)
        integrator = adapter.integrator
        existing_rooms = self.repository.list_existing_rooms(floor_plan_id)
        try:
            result, _metadata = adapter.recognize(
                str(image_path),
                floor_plan_id=floor_plan_id,
                debug_dir=str(debug_dir) if debug_dir else None,
            )
            recognition_payload = integrator.result_to_dict(result)
            walls, doors, windows, rooms, dimensions = integrator.convert_to_database_models(
                result,
                floor_plan_id,
                scale_factor_mm_per_px=floor_plan.scale_factor or 1.0,
            )
            self._preserve_room_names(existing_rooms, rooms)

            recognition = self.repository.get_recognition(floor_plan_id)
            if recognition is None:
                recognition = self.repository.create_recognition(
                    {
                        "floor_plan_id": floor_plan_id,
                        "recognition_result": recognition_payload,
                        "status": "completed",
                        "error_message": None,
                        "debug_artifacts_dir": f"debug_output/floor_plan_{floor_plan_id}" if debug_dir else None,
                    }
                )
                self.repository.add(recognition)
            else:
                recognition.recognition_result = recognition_payload
                recognition.status = "completed"
                recognition.error_message = None
                recognition.debug_artifacts_dir = f"debug_output/floor_plan_{floor_plan_id}" if debug_dir else None

            self.repository.replace_detection_result(
                floor_plan_id,
                walls=[],
                doors=[],
                windows=[],
                rooms=[],
                dimensions=[],
            )
            for wall in walls:
                self.repository.add(wall)
            self.repository.flush()
            wall_id_map = self._build_wall_id_map(walls)

            for door in doors:
                if door.wall_id is not None:
                    door.wall_id = wall_id_map.get(int(door.wall_id))
                self.repository.add(door)
            for window in windows:
                if window.wall_id is not None:
                    window.wall_id = wall_id_map.get(int(window.wall_id))
                self.repository.add(window)
            for room in rooms:
                self.repository.add(room)

            self.repository.flush()
            room_id_map = self._build_room_id_map(rooms)

            for dimension in dimensions:
                if dimension.wall_id is not None:
                    dimension.wall_id = wall_id_map.get(int(dimension.wall_id))
                if dimension.room_id is not None:
                    dimension.room_id = room_id_map.get(int(dimension.room_id))
                self.repository.add(dimension)
            self.repository.flush()
            recognition_id = recognition.id
            self.uow.commit()
            self.events.publish(
                "recognition_completed",
                {"category": "recognition", "use_case": "ProcessFloorPlan", "floor_plan_id": floor_plan_id},
            )
            return recognition_id, len(walls), len(doors), len(windows), len(rooms), len(dimensions)
        except AppError:
            self.uow.rollback()
            raise
        except Exception as exc:
            self.uow.rollback()
            logger.exception("Recognition failed for floor plan %s", floor_plan_id)
            recognition = self.repository.get_recognition(floor_plan_id)
            failure_payload = {"error": str(exc)}
            if recognition is None:
                recognition = self.repository.create_recognition(
                    {
                        "floor_plan_id": floor_plan_id,
                        "recognition_result": failure_payload,
                        "status": "failed",
                        "error_message": str(exc),
                        "debug_artifacts_dir": f"debug_output/floor_plan_{floor_plan_id}" if debug_dir else None,
                    }
                )
                self.repository.add(recognition)
            else:
                recognition.recognition_result = failure_payload
                recognition.status = "failed"
                recognition.error_message = str(exc)
                recognition.debug_artifacts_dir = f"debug_output/floor_plan_{floor_plan_id}" if debug_dir else None
            self.uow.commit()
            self.events.publish(
                "recognition_failed",
                {"category": "recognition", "use_case": "ProcessFloorPlan", "floor_plan_id": floor_plan_id, "payload": {"error": str(exc)}},
            )
            raise AppError(500, "recognition_failed", f"Error processing floor plan: {exc}") from exc

    def get_recognition(self, floor_plan_id: int, debug: bool = False) -> RecognitionRead:
        recognition = self.repository.get_recognition(floor_plan_id)
        if recognition is None:
            return RecognitionRead(
                id=None,
                floor_plan_id=floor_plan_id,
                status="not_processed",
                recognition_result=None,
                error_message=None,
                processed_at=None,
                debug_artifacts_dir=None,
                debug_images=[],
            )

        result = RecognitionRead.model_validate(RecognitionRecord.from_model(recognition).to_dict())
        if debug:
            result.debug_images = self.storage.list_debug_images(result.debug_artifacts_dir)
        return result

    def submit_feedback_sample(self, floor_plan_id: int) -> RecognitionFeedbackRead:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        recognition = self.repository.get_recognition(floor_plan_id)
        if recognition is None:
            raise AppError(404, "recognition_not_found", "Recognition result not found for floor plan")
        if recognition.status != "completed" or recognition.recognition_result is None:
            raise AppError(409, "recognition_not_completed", "Recognition must complete before feedback can be submitted")

        now = datetime.now(timezone.utc)
        snapshot = self._build_corrected_snapshot(floor_plan.to_dict(include_elements=True))
        sample = self.repository.get_feedback_sample(recognition.id)
        if sample is None:
            sample = self.repository.create_feedback_sample(
                {
                    "floor_plan_id": floor_plan_id,
                    "recognition_id": recognition.id,
                    "original_image_path": floor_plan.original_image_path,
                    "source_recognition_result": recognition.recognition_result,
                    "corrected_snapshot": snapshot,
                    "status": "approved",
                    "submitted_at": now,
                    "exported_at": None,
                    "export_batch_id": None,
                }
            )
            self.repository.add(sample)
        else:
            sample.original_image_path = floor_plan.original_image_path
            sample.source_recognition_result = recognition.recognition_result
            sample.corrected_snapshot = snapshot
            sample.status = "approved"
            sample.submitted_at = now
            sample.exported_at = None
            sample.export_batch_id = None

        self.repository.flush()
        self.uow.commit()
        self.events.publish(
            "recognition_feedback_submitted",
            {"category": "recognition", "use_case": "SubmitRecognitionFeedback", "floor_plan_id": floor_plan_id},
        )
        return RecognitionFeedbackRead.model_validate(sample)

    def export_feedback_samples(
        self,
        *,
        batch_id: str | None = None,
        output_root: Path | None = None,
    ) -> dict[str, Any]:
        export_batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
        export_root = Path(output_root or (settings.outputs_dir / "recognition_feedback"))
        batch_dir = export_root / export_batch_id
        images_dir = batch_dir / "images"
        annotations_dir = batch_dir / "annotations"
        images_dir.mkdir(parents=True, exist_ok=True)
        annotations_dir.mkdir(parents=True, exist_ok=True)

        samples = self.repository.list_feedback_samples_for_export()
        exported_at = datetime.now(timezone.utc)
        manifest_lines: list[str] = []
        exported_count = 0
        try:
            for sample in samples:
                source_path = self.storage.absolute_path(sample.original_image_path)
                if source_path is None or not source_path.exists():
                    raise AppError(
                        400,
                        "recognition_feedback_source_missing",
                        f"Source image for feedback sample {sample.id} is missing",
                    )
                image_name = f"sample_{sample.id}_recognition_{sample.recognition_id}{source_path.suffix or '.bin'}"
                annotation_name = f"sample_{sample.id}_recognition_{sample.recognition_id}.json"
                image_target = images_dir / image_name
                annotation_target = annotations_dir / annotation_name
                shutil.copy2(source_path, image_target)
                self._write_json(annotation_target, sample.corrected_snapshot)
                manifest_lines.append(
                    json.dumps(
                        {
                            "sample_id": sample.id,
                            "floor_plan_id": sample.floor_plan_id,
                            "recognition_id": sample.recognition_id,
                            "image_path": f"images/{image_name}",
                            "annotation_path": f"annotations/{annotation_name}",
                            "original_image_path": sample.original_image_path,
                            "source_recognition_result": sample.source_recognition_result,
                            "submitted_at": sample.submitted_at.isoformat() if sample.submitted_at else None,
                            "exported_at": exported_at.isoformat(),
                        },
                        ensure_ascii=False,
                    )
                )
                sample.status = "exported"
                sample.exported_at = exported_at
                sample.export_batch_id = export_batch_id
                exported_count += 1

            manifest_path = batch_dir / "manifest.jsonl"
            manifest_path.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")
            self.repository.flush()
            self.uow.commit()
        except Exception:
            self.uow.rollback()
            raise

        self.events.publish(
            "recognition_feedback_exported",
            {
                "category": "recognition",
                "use_case": "ExportRecognitionFeedback",
                "payload": {"batch_id": export_batch_id, "count": exported_count},
            },
        )
        return {
            "batch_id": export_batch_id,
            "export_dir": str(batch_dir.resolve()),
            "count": exported_count,
        }

    @staticmethod
    def _build_wall_id_map(walls: Iterable) -> Dict[int, int]:
        mapping: Dict[int, int] = {}
        for wall in walls:
            material = wall.material or ""
            match = re.match(r"detected_wall_(\d+)", material)
            if match:
                mapping[int(match.group(1))] = wall.id
        return mapping

    @staticmethod
    def _build_room_id_map(rooms: Iterable) -> Dict[int, int]:
        mapping: Dict[int, int] = {}
        for room in rooms:
            if room.room_number is None:
                continue
            try:
                rec_room_id = int(room.room_number)
            except (TypeError, ValueError):
                continue
            mapping[rec_room_id] = room.id
        return mapping

    def _preserve_room_names(self, existing_rooms: list, new_rooms: list) -> None:
        if not existing_rooms or not new_rooms:
            return
        named_existing = [room for room in existing_rooms if room.name and room.boundary_points]
        if not named_existing:
            return
        used_new_indices: set[int] = set()
        for old_room in named_existing:
            best_idx = None
            best_iou = 0.0
            for idx, new_room in enumerate(new_rooms):
                if idx in used_new_indices or not new_room.boundary_points:
                    continue
                iou = self._polygon_iou(old_room.boundary_points, new_room.boundary_points)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx
            if best_idx is not None and best_iou >= 0.5:
                new_rooms[best_idx].name = old_room.name
                used_new_indices.add(best_idx)

    @staticmethod
    def _polygon_iou(poly1: List[List[float]], poly2: List[List[float]]) -> float:
        if not poly1 or not poly2 or len(poly1) < 3 or len(poly2) < 3:
            return 0.0

        arr1 = np.array(poly1, dtype=np.float32)
        arr2 = np.array(poly2, dtype=np.float32)
        min_x = int(np.floor(min(arr1[:, 0].min(), arr2[:, 0].min()))) - 2
        min_y = int(np.floor(min(arr1[:, 1].min(), arr2[:, 1].min()))) - 2
        max_x = int(np.ceil(max(arr1[:, 0].max(), arr2[:, 0].max()))) + 2
        max_y = int(np.ceil(max(arr1[:, 1].max(), arr2[:, 1].max()))) + 2
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        if width <= 2 or height <= 2:
            return 0.0

        shifted1 = (arr1 - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32).reshape((-1, 1, 2))
        shifted2 = (arr2 - np.array([min_x, min_y], dtype=np.float32)).astype(np.int32).reshape((-1, 1, 2))
        mask1 = np.zeros((height, width), dtype=np.uint8)
        mask2 = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask1, [shifted1], 255)
        cv2.fillPoly(mask2, [shifted2], 255)
        intersection = np.logical_and(mask1 > 0, mask2 > 0).sum()
        union = np.logical_or(mask1 > 0, mask2 > 0).sum()
        if union == 0:
            return 0.0
        return float(intersection) / float(union)

    @staticmethod
    def _build_corrected_snapshot(floor_plan_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "walls": floor_plan_data.get("walls") or [],
            "doors": floor_plan_data.get("doors") or [],
            "windows": floor_plan_data.get("windows") or [],
            "rooms": floor_plan_data.get("rooms") or [],
            "dimensions": floor_plan_data.get("dimensions") or [],
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

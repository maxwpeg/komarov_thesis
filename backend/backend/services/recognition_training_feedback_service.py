"""Step-level feedback capture and export helpers for recognition retraining."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from backend.config import settings
from backend.errors import AppError
from backend.models import (
    FloorPlan,
    FloorplanRecognition,
    PipelineDetectionSnapshot,
    RecognitionFeedbackExample,
    RecognitionTrainingBatch,
    RecognitionTrainingBatchExample,
)
from backend.modules.pipeline.domain.state import PipelineStateModel


SUPPORTED_FEEDBACK_STEPS = ("walls", "openings")
DETECTOR_VERSION = "cv.hybrid.v1"
MAX_IDLE_DAYS = 14
MIN_REAL_CORRECTION_RATIO = 0.2
HARD_EXAMPLE_THRESHOLD = 3.0
WALL_BATCH_MIN_APPROVED = 50
WALL_BATCH_MIN_HARD = 10
OPENINGS_BATCH_MIN_APPROVED = 75
OPENINGS_BATCH_MIN_LABELED = 200
TRAINING_PARAMETER_DEFAULTS = {
    "walls": {
        "model": "assets/models/yolov8n-seg.pt",
        "epochs": 80,
        "imgsz": 1024,
        "batch": -1,
        "patience": 15,
        "device": "auto",
    },
    "openings": {
        "model": "assets/models/yolov8n-seg.pt",
        "epochs": 120,
        "imgsz": 1280,
        "batch": -1,
        "patience": 20,
        "device": "auto",
    },
}

UTC_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    """Normalize legacy SQLite datetimes to aware UTC values."""
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class RecognitionTrainingFeedbackService:
    """Captures training-ready feedback snapshots for walls and openings."""

    db: Session
    storage: Any

    def save_detection_snapshot(
        self,
        floor_plan: FloorPlan,
        *,
        step: str,
        step_revision: int,
        detector_version: str | None = None,
    ) -> PipelineDetectionSnapshot:
        self._ensure_supported_step(step)
        payload = self.build_step_snapshot(floor_plan, step)
        effective_detector_version = str(detector_version or DETECTOR_VERSION)
        existing = (
            self.db.query(PipelineDetectionSnapshot)
            .filter(
                PipelineDetectionSnapshot.floor_plan_id == floor_plan.id,
                PipelineDetectionSnapshot.step == step,
                PipelineDetectionSnapshot.step_revision == step_revision,
            )
            .order_by(PipelineDetectionSnapshot.id.asc())
            .first()
        )
        if existing is None:
            existing = PipelineDetectionSnapshot(
                floor_plan_id=floor_plan.id,
                step=step,
                step_revision=step_revision,
                detector_version=effective_detector_version,
                source_snapshot=payload,
            )
            self.db.add(existing)
        else:
            existing.detector_version = effective_detector_version
            existing.source_snapshot = payload
            existing.created_at = datetime.now(timezone.utc)
        self.db.flush()
        return existing

    def get_feedback_step_state(self, floor_plan_id: int, step: str, step_revision: int) -> dict[str, Any]:
        example = self.get_feedback_example(floor_plan_id, step, step_revision)
        if example is None:
            return {
                "feedback_status": None,
                "feedback_example_id": None,
                "feedback_submitted_at": None,
                "feedback_submitted_revision": None,
            }
        return {
            "feedback_status": example.status,
            "feedback_example_id": example.id,
            "feedback_submitted_at": example.submitted_at,
            "feedback_submitted_revision": example.step_revision,
        }

    def get_feedback_example(
        self,
        floor_plan_id: int,
        step: str,
        step_revision: int,
    ) -> RecognitionFeedbackExample | None:
        return (
            self.db.query(RecognitionFeedbackExample)
            .filter(
                RecognitionFeedbackExample.floor_plan_id == floor_plan_id,
                RecognitionFeedbackExample.step == step,
                RecognitionFeedbackExample.step_revision == step_revision,
            )
            .order_by(RecognitionFeedbackExample.id.asc())
            .first()
        )

    def submit_step_feedback(
        self,
        floor_plan_id: int,
        *,
        step: str,
        step_revision: int,
        issue_tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_supported_step(step)
        floor_plan = self._get_floor_plan(floor_plan_id)
        pipeline_state = PipelineStateModel.normalize(
            floor_plan.pipeline_state,
            floor_plan.active_signal_system_type,
        )
        step_state = pipeline_state.steps[step]
        if step_state.status != "validated":
            raise AppError(409, "pipeline_step_not_validated", f"{step.title()} must be validated before feedback submission")
        if int(step_state.revision or 0) != int(step_revision):
            raise AppError(
                409,
                "feedback_revision_mismatch",
                f"Expected revision {step_state.revision} for {step}, got {step_revision}",
            )

        snapshot = self._get_or_create_detection_snapshot(
            floor_plan,
            step=step,
            step_revision=step_revision,
        )

        corrected_snapshot = self.build_step_snapshot(floor_plan, step)
        diff_summary = self._compute_diff_summary(step, snapshot.source_snapshot, corrected_snapshot)
        recognition = (
            self.db.query(FloorplanRecognition)
            .filter(FloorplanRecognition.floor_plan_id == floor_plan_id)
            .first()
        )
        example = self.get_feedback_example(floor_plan_id, step, step_revision)
        now = datetime.now(timezone.utc)
        normalized_tags = [str(tag).strip() for tag in (issue_tags or []) if str(tag).strip()]
        if example is None:
            example = RecognitionFeedbackExample(
                floor_plan_id=floor_plan_id,
                recognition_id=recognition.id if recognition else None,
                step=step,
                step_revision=step_revision,
                detector_version=snapshot.detector_version or DETECTOR_VERSION,
                source_snapshot=snapshot.source_snapshot,
                corrected_snapshot=corrected_snapshot,
                diff_summary=diff_summary,
                issue_tags=normalized_tags,
                notes=(notes or "").strip() or None,
                hardness_score=float(diff_summary.get("hardness_score", 0.0) or 0.0),
                status="approved",
                curation_status="approved",
                curated_at=now,
                submitted_at=now,
            )
            self.db.add(example)
        else:
            example.recognition_id = recognition.id if recognition else None
            example.detector_version = snapshot.detector_version or DETECTOR_VERSION
            example.source_snapshot = snapshot.source_snapshot
            example.corrected_snapshot = corrected_snapshot
            example.diff_summary = diff_summary
            example.issue_tags = normalized_tags
            example.notes = (notes or "").strip() or None
            example.hardness_score = float(diff_summary.get("hardness_score", 0.0) or 0.0)
            example.status = "approved"
            example.curation_status = "approved"
            example.curated_at = now
            example.training_batch_id = None
            example.submitted_at = now
            example.batched_at = None
            example.exported_at = None
            example.used_at = None

        self.db.flush()
        step_stats = self._build_step_stats(step)
        return {
            "feedback_id": example.id,
            "step": step,
            "status": example.status,
            "submitted_revision": step_revision,
            "pending_counts": step_stats["pending_counts"],
            "next_batch_hint": step_stats["next_batch_hint"],
        }

    def _get_or_create_detection_snapshot(
        self,
        floor_plan: FloorPlan,
        *,
        step: str,
        step_revision: int,
    ) -> PipelineDetectionSnapshot:
        snapshot = (
            self.db.query(PipelineDetectionSnapshot)
            .filter(
                PipelineDetectionSnapshot.floor_plan_id == floor_plan.id,
                PipelineDetectionSnapshot.step == step,
                PipelineDetectionSnapshot.step_revision == step_revision,
            )
            .order_by(PipelineDetectionSnapshot.id.asc())
            .first()
        )
        if snapshot is not None:
            return snapshot

        # Legacy floor plans can have validated revisions created before
        # detector snapshots were persisted. Backfill from the current step
        # state so feedback submission still works for those plans.
        payload = self.build_step_snapshot(floor_plan, step)
        payload["source_kind"] = "legacy_backfill_current_state"
        snapshot = PipelineDetectionSnapshot(
            floor_plan_id=floor_plan.id,
            step=step,
            step_revision=step_revision,
            detector_version=DETECTOR_VERSION,
            source_snapshot=payload,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get_feedback_stats(self) -> dict[str, Any]:
        return {
            "detector_version": DETECTOR_VERSION,
            "steps": [self._build_step_stats(step) for step in SUPPORTED_FEEDBACK_STEPS],
        }

    def get_step_stats(self, step: str) -> dict[str, Any]:
        return self._build_step_stats(step)

    def get_step_thresholds(self, step: str) -> dict[str, Any]:
        self._ensure_supported_step(step)
        return self._step_thresholds(step)

    def select_examples_for_batch(self, step: str) -> tuple[list[RecognitionFeedbackExample], dict[str, Any]]:
        return self._select_examples_for_batch(step)

    def export_feedback_batch(
        self,
        step: str,
        *,
        batch_id: str | None = None,
        output_root: Path | None = None,
        commit: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        self._ensure_supported_step(step)
        export_root = Path(output_root or (settings.outputs_dir / "recognition_feedback"))
        export_root.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        base_id = batch_id or (
            datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
        )
        examples, hint = self._select_examples_for_batch(step)
        if not examples or (not hint["eligible"] and not force):
            return {
                "batch": None,
                "skipped": {
                    "step": step,
                    "reason": hint["reason"],
                    "approved_examples": hint["approved_examples"],
                    "selected_examples": hint["selected_examples"],
                },
            }

        step_batch_id = f"{base_id}_{step}"
        batch_dir = export_root / step_batch_id
        images_dir = batch_dir / "images"
        native_source_dir = batch_dir / "native" / "source"
        native_corrected_dir = batch_dir / "native" / "corrected"
        derived_dir = batch_dir / "derived"
        images_dir.mkdir(parents=True, exist_ok=True)
        native_source_dir.mkdir(parents=True, exist_ok=True)
        native_corrected_dir.mkdir(parents=True, exist_ok=True)
        derived_dir.mkdir(parents=True, exist_ok=True)

        batch_model = RecognitionTrainingBatch(
            batch_id=step_batch_id,
            step=step,
            detector_version=DETECTOR_VERSION,
            status="exported",
            export_dir=str(batch_dir.resolve()),
            summary={},
            created_at=now,
            exported_at=now,
        )
        self.db.add(batch_model)
        self.db.flush()

        manifest_entries: list[dict[str, Any]] = []
        for example in examples:
            manifest_entries.append(
                self._export_example(
                    example,
                    step=step,
                    batch_dir=batch_dir,
                    images_dir=images_dir,
                    native_source_dir=native_source_dir,
                    native_corrected_dir=native_corrected_dir,
                    derived_dir=derived_dir,
                )
            )
            self.db.add(
                RecognitionTrainingBatchExample(
                    training_batch_id=batch_model.id,
                    feedback_example_id=example.id,
                    included_at=now,
                )
            )
            example.training_batch_id = batch_model.id
            example.status = "exported"
            example.batched_at = now
            example.exported_at = now

        manifest_path = batch_dir / "manifest.jsonl"
        manifest_path.write_text(
            "\n".join(json.dumps(entry, ensure_ascii=False) for entry in manifest_entries) + ("\n" if manifest_entries else ""),
            encoding="utf-8",
        )
        summary = {
            "sample_count": len(examples),
            "hard_examples": sum(1 for item in examples if float(item.hardness_score or 0.0) >= HARD_EXAMPLE_THRESHOLD),
            "real_correction_examples": sum(1 for item in examples if bool((item.diff_summary or {}).get("changed"))),
            "manifest_path": str(manifest_path.resolve()),
            "split_counts": self._count_splits(manifest_entries),
            "forced": bool(force),
        }
        batch_model.summary = summary
        result = {
            "batch": {
                "id": batch_model.id,
                "batch_id": step_batch_id,
                "step": step,
                "export_dir": str(batch_dir.resolve()),
                "count": len(examples),
                "summary": summary,
                "forced": bool(force),
            },
            "skipped": None,
        }
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return result

    def export_feedback_batches(
        self,
        *,
        batch_id: str | None = None,
        output_root: Path | None = None,
        steps: tuple[str, ...] = SUPPORTED_FEEDBACK_STEPS,
    ) -> dict[str, Any]:
        exported_batches: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        base_id = batch_id or (datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + f"_{uuid.uuid4().hex[:8]}")

        for step in steps:
            export_result = self.export_feedback_batch(
                step,
                batch_id=base_id,
                output_root=output_root,
                commit=False,
            )
            if export_result["batch"] is not None:
                exported_batches.append(export_result["batch"])
            elif export_result["skipped"] is not None:
                skipped.append(export_result["skipped"])

        self.db.commit()
        return {
            "detector_version": DETECTOR_VERSION,
            "batches": exported_batches,
            "skipped": skipped,
        }

    def build_step_snapshot(self, floor_plan: FloorPlan, step: str) -> dict[str, Any]:
        self._ensure_supported_step(step)
        image_meta = {
            "width": floor_plan.image_width,
            "height": floor_plan.image_height,
            "original_image_path": floor_plan.original_image_path,
            "scale_factor": floor_plan.scale_factor,
        }
        if step == "walls":
            return {
                "step": step,
                "image": image_meta,
                "walls": [self._serialize_wall(wall) for wall in floor_plan.walls],
                "dimensions": [self._serialize_dimension(dimension) for dimension in floor_plan.dimensions],
            }
        return {
            "step": step,
            "image": image_meta,
            "walls": [self._serialize_wall(wall) for wall in floor_plan.walls],
            "openings": [self._serialize_door(door) for door in floor_plan.doors] + [self._serialize_window(window) for window in floor_plan.windows],
        }

    def _build_step_stats(self, step: str) -> dict[str, Any]:
        self._ensure_supported_step(step)
        examples = (
            self.db.query(RecognitionFeedbackExample)
            .filter(RecognitionFeedbackExample.step == step)
            .order_by(RecognitionFeedbackExample.submitted_at.asc(), RecognitionFeedbackExample.id.asc())
            .all()
        )
        pending_counts = self._count_examples_by_status(examples)
        hint = self._build_batch_hint(
            step,
            [example for example in examples if (example.curation_status or "approved") == "approved"],
        )
        last_batch = (
            self.db.query(RecognitionTrainingBatch)
            .filter(RecognitionTrainingBatch.step == step)
            .order_by(RecognitionTrainingBatch.exported_at.desc(), RecognitionTrainingBatch.created_at.desc())
            .first()
        )
        return {
            "step": step,
            "detector_version": DETECTOR_VERSION,
            "pending_counts": pending_counts,
            "thresholds": self._step_thresholds(step),
            "next_batch_hint": hint,
            "last_batch": last_batch.to_dict() if last_batch is not None else None,
        }

    def _select_examples_for_batch(self, step: str) -> tuple[list[RecognitionFeedbackExample], dict[str, Any]]:
        approved_examples = (
            self.db.query(RecognitionFeedbackExample)
            .filter(
                RecognitionFeedbackExample.step == step,
                RecognitionFeedbackExample.curation_status == "approved",
            )
            .order_by(RecognitionFeedbackExample.submitted_at.asc(), RecognitionFeedbackExample.id.asc())
            .all()
        )
        hint = self._build_batch_hint(step, approved_examples)
        changed = [
            example
            for example in approved_examples
            if bool((example.diff_summary or {}).get("changed"))
        ]
        unchanged = [
            example
            for example in approved_examples
            if not bool((example.diff_summary or {}).get("changed"))
        ]
        changed_sorted = sorted(
            changed,
            key=lambda item: (
                -float(item.hardness_score or 0.0),
                _coerce_utc_datetime(item.submitted_at) or UTC_MIN_DATETIME,
                item.id,
            ),
        )
        unchanged_sorted = sorted(
            unchanged,
            key=lambda item: (_coerce_utc_datetime(item.submitted_at) or UTC_MIN_DATETIME, item.id),
        )
        max_unchanged = len(changed_sorted) * 4 if changed_sorted else 0
        selected = changed_sorted + unchanged_sorted[:max_unchanged]
        selected_ids = {item.id for item in selected}
        selected = [item for item in approved_examples if item.id in selected_ids]
        hint["selected_examples"] = len(selected)
        return selected, hint

    def _build_batch_hint(self, step: str, approved_examples: list[RecognitionFeedbackExample]) -> dict[str, Any]:
        last_batch = (
            self.db.query(RecognitionTrainingBatch)
            .filter(RecognitionTrainingBatch.step == step)
            .order_by(RecognitionTrainingBatch.exported_at.desc(), RecognitionTrainingBatch.created_at.desc())
            .first()
        )
        changed_examples = [
            example
            for example in approved_examples
            if bool((example.diff_summary or {}).get("changed"))
        ]
        hard_examples = [
            example
            for example in approved_examples
            if float(example.hardness_score or 0.0) >= HARD_EXAMPLE_THRESHOLD
        ]
        selected_count = len(changed_examples) + min(len(approved_examples) - len(changed_examples), len(changed_examples) * 4)
        real_ratio = (len(changed_examples) / selected_count) if selected_count else 0.0
        idle_due = self._is_idle_due(last_batch)
        hint = {
            "step": step,
            "eligible": False,
            "reason": "not_ready",
            "approved_examples": len(approved_examples),
            "selected_examples": selected_count,
            "real_correction_examples": len(changed_examples),
            "hard_examples": len(hard_examples),
            "pending_examples": len(approved_examples),
            "labeled_openings": 0,
            "has_door_examples": False,
            "has_window_examples": False,
            "last_batch_id": last_batch.batch_id if last_batch is not None else None,
        }
        if selected_count == 0:
            hint["reason"] = "no_approved_examples"
            return hint
        if real_ratio < MIN_REAL_CORRECTION_RATIO:
            hint["reason"] = "insufficient_real_corrections"
            return hint

        if step == "walls":
            if selected_count >= WALL_BATCH_MIN_APPROVED:
                hint["eligible"] = True
                hint["reason"] = "approved_examples_threshold_met"
            elif idle_due and len(hard_examples) >= WALL_BATCH_MIN_HARD:
                hint["eligible"] = True
                hint["reason"] = "idle_window_and_hard_examples_met"
            else:
                hint["reason"] = "waiting_for_more_wall_examples"
            return hint

        labeled_openings = 0
        has_door_examples = False
        has_window_examples = False
        for example in approved_examples:
            corrected_openings = self._snapshot_openings(example.corrected_snapshot)
            labeled_openings += len(corrected_openings)
            has_door_examples = has_door_examples or any(item["type"] == "door" for item in corrected_openings)
            has_window_examples = has_window_examples or any(item["type"] == "window" for item in corrected_openings)
        hint["labeled_openings"] = labeled_openings
        hint["has_door_examples"] = has_door_examples
        hint["has_window_examples"] = has_window_examples
        if selected_count >= OPENINGS_BATCH_MIN_APPROVED:
            hint["eligible"] = True
            hint["reason"] = "approved_examples_threshold_met"
        elif idle_due and labeled_openings >= OPENINGS_BATCH_MIN_LABELED and has_door_examples and has_window_examples:
            hint["eligible"] = True
            hint["reason"] = "idle_window_and_label_requirements_met"
        else:
            hint["reason"] = "waiting_for_more_opening_examples"
        return hint

    def _export_example(
        self,
        example: RecognitionFeedbackExample,
        *,
        step: str,
        batch_dir: Path,
        images_dir: Path,
        native_source_dir: Path,
        native_corrected_dir: Path,
        derived_dir: Path,
    ) -> dict[str, Any]:
        source_path = self.storage.absolute_path(example.floor_plan.original_image_path)
        if source_path is None or not source_path.exists():
            raise AppError(
                400,
                "feedback_source_image_missing",
                f"Source image for feedback example {example.id} is missing",
            )
        image_name = f"sample_{example.id}_plan_{example.floor_plan_id}{source_path.suffix or '.bin'}"
        image_target = images_dir / image_name
        shutil.copy2(source_path, image_target)

        source_json_name = f"sample_{example.id}_source.json"
        corrected_json_name = f"sample_{example.id}_corrected.json"
        source_json_target = native_source_dir / source_json_name
        corrected_json_target = native_corrected_dir / corrected_json_name
        self._write_json(source_json_target, example.source_snapshot)
        self._write_json(corrected_json_target, example.corrected_snapshot)

        split = self._dataset_split(example.floor_plan_id)
        if step == "walls":
            derived_payload = self._export_wall_derived_assets(
                example,
                derived_dir=derived_dir,
            )
        else:
            derived_payload = self._export_openings_derived_assets(
                example,
                image_path=source_path,
                derived_dir=derived_dir,
            )

        return {
            "sample_id": example.id,
            "floor_plan_id": example.floor_plan_id,
            "step": example.step,
            "step_revision": example.step_revision,
            "detector_version": example.detector_version,
            "split": split,
            "image_path": f"images/{image_name}",
            "source_snapshot_path": f"native/source/{source_json_name}",
            "corrected_snapshot_path": f"native/corrected/{corrected_json_name}",
            "diff_summary": example.diff_summary,
            "issue_tags": example.issue_tags or [],
            "hardness_score": example.hardness_score,
            "curation_status": example.curation_status,
            "derived": derived_payload,
        }

    def _export_wall_derived_assets(
        self,
        example: RecognitionFeedbackExample,
        *,
        derived_dir: Path,
    ) -> dict[str, Any]:
        mask_dir = derived_dir / "wall_masks"
        centerline_dir = derived_dir / "centerlines"
        mask_dir.mkdir(parents=True, exist_ok=True)
        centerline_dir.mkdir(parents=True, exist_ok=True)

        image_meta = example.corrected_snapshot.get("image") or {}
        width = int(image_meta.get("width") or 0)
        height = int(image_meta.get("height") or 0)
        scale_factor = float(image_meta.get("scale_factor") or 1.0 or 1.0)
        if width <= 0 or height <= 0:
            raise AppError(400, "feedback_image_metadata_missing", "Image metadata is required to export wall masks")

        wall_mask = np.zeros((height, width), dtype=np.uint8)
        for wall in example.corrected_snapshot.get("walls") or []:
            thickness_mm = float(wall.get("thickness", wall.get("thickness_px", 1)) or 1)
            thickness = max(1, int(round(thickness_mm / max(scale_factor, 1e-6))))
            cv2.line(
                wall_mask,
                (int(round(float(wall["x1"]))), int(round(float(wall["y1"])))),
                (int(round(float(wall["x2"]))), int(round(float(wall["y2"])))),
                color=255,
                thickness=thickness,
            )

        mask_name = f"sample_{example.id}_walls.png"
        centerline_name = f"sample_{example.id}_centerlines.json"
        mask_path = mask_dir / mask_name
        centerline_path = centerline_dir / centerline_name
        cv2.imwrite(str(mask_path), wall_mask)
        self._write_json(
            centerline_path,
            {
                "walls": example.corrected_snapshot.get("walls") or [],
                "image": image_meta,
            },
        )
        return {
            "wall_mask_path": f"derived/wall_masks/{mask_name}",
            "centerlines_path": f"derived/centerlines/{centerline_name}",
        }

    def _export_openings_derived_assets(
        self,
        example: RecognitionFeedbackExample,
        *,
        image_path: Path,
        derived_dir: Path,
    ) -> dict[str, Any]:
        crop_dir = derived_dir / "roi_crops"
        annotation_dir = derived_dir / "roi_annotations"
        crop_dir.mkdir(parents=True, exist_ok=True)
        annotation_dir.mkdir(parents=True, exist_ok=True)

        image = cv2.imread(str(image_path))
        if image is None:
            raise AppError(400, "feedback_source_image_unreadable", f"Could not read source image {image_path}")

        corrected_openings = self._snapshot_openings(example.corrected_snapshot)
        source_openings = self._snapshot_openings(example.source_snapshot)
        source_walls = {
            int(item["id"]): item
            for item in (example.source_snapshot.get("walls") or [])
            if item.get("id") is not None
        }
        corrected_walls = {
            int(item["id"]): item
            for item in (example.corrected_snapshot.get("walls") or [])
            if item.get("id") is not None
        }
        matches = self._match_openings(source_openings, corrected_openings)
        matched_source = {src_idx for src_idx, _corr_idx, _score in matches}

        crops: list[dict[str, Any]] = []
        crop_index = 1
        for opening in corrected_openings:
            wall = corrected_walls.get(int(opening["wall_id"])) if opening.get("wall_id") is not None else None
            crop_entry = self._write_opening_crop(
                image=image,
                bbox=opening["bbox"],
                wall=wall,
                crop_dir=crop_dir,
                annotation_dir=annotation_dir,
                example_id=example.id,
                crop_index=crop_index,
                label=opening["type"],
                metadata={
                    "source": "corrected",
                    "opening": opening,
                },
            )
            crops.append(crop_entry)
            crop_index += 1

        for src_idx, opening in enumerate(source_openings):
            if src_idx in matched_source:
                continue
            wall = source_walls.get(int(opening["wall_id"])) if opening.get("wall_id") is not None else None
            crop_entry = self._write_opening_crop(
                image=image,
                bbox=opening["bbox"],
                wall=wall,
                crop_dir=crop_dir,
                annotation_dir=annotation_dir,
                example_id=example.id,
                crop_index=crop_index,
                label="none",
                metadata={
                    "source": "unmatched_source",
                    "opening": opening,
                },
            )
            crops.append(crop_entry)
            crop_index += 1

        return {
            "crops": crops,
        }

    def _write_opening_crop(
        self,
        *,
        image: np.ndarray,
        bbox: list[float] | tuple[float, float, float, float],
        wall: dict[str, Any] | None,
        crop_dir: Path,
        annotation_dir: Path,
        example_id: int,
        crop_index: int,
        label: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        x1, y1, x2, y2 = [float(value) for value in bbox]
        width = max(1.0, x2 - x1)
        height = max(1.0, y2 - y1)
        padding = max(12, int(round(max(width, height) * 0.6)))
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        x_start = max(0, int(math.floor(cx - width / 2.0 - padding)))
        y_start = max(0, int(math.floor(cy - height / 2.0 - padding)))
        x_end = min(image.shape[1], int(math.ceil(cx + width / 2.0 + padding)))
        y_end = min(image.shape[0], int(math.ceil(cy + height / 2.0 + padding)))
        patch = image[y_start:y_end, x_start:x_end]
        if patch.size == 0:
            raise AppError(400, "feedback_crop_out_of_bounds", "Computed crop for opening feedback is empty")

        angle = self._wall_angle_deg(wall) if wall else 0.0
        rotation_matrix = cv2.getRotationMatrix2D((patch.shape[1] / 2.0, patch.shape[0] / 2.0), -angle, 1.0)
        rotated = cv2.warpAffine(
            patch,
            rotation_matrix,
            (patch.shape[1], patch.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        crop_name = f"sample_{example_id}_crop_{crop_index:03d}.png"
        crop_path = crop_dir / crop_name
        cv2.imwrite(str(crop_path), rotated)
        annotation_name = f"sample_{example_id}_crop_{crop_index:03d}.json"
        annotation_path = annotation_dir / annotation_name
        payload = {
            "label": label,
            "wall_angle_deg": angle,
            "crop_bbox": [x_start, y_start, x_end, y_end],
            "original_bbox": [x1, y1, x2, y2],
            **metadata,
        }
        self._write_json(annotation_path, payload)
        return {
            "image_path": f"derived/roi_crops/{crop_name}",
            "annotation_path": f"derived/roi_annotations/{annotation_name}",
            "label": label,
        }

    def _compute_diff_summary(self, step: str, source_snapshot: dict[str, Any], corrected_snapshot: dict[str, Any]) -> dict[str, Any]:
        if step == "walls":
            return self._build_wall_diff_summary(source_snapshot, corrected_snapshot)
        return self._build_openings_diff_summary(source_snapshot, corrected_snapshot)

    def _build_wall_diff_summary(self, source_snapshot: dict[str, Any], corrected_snapshot: dict[str, Any]) -> dict[str, Any]:
        source_walls = source_snapshot.get("walls") or []
        corrected_walls = corrected_snapshot.get("walls") or []
        match_pairs, source_candidate_counts, corrected_candidate_counts = self._match_walls(source_walls, corrected_walls)
        matched_source = {src_idx for src_idx, _corr_idx, _score in match_pairs}
        matched_corrected = {corr_idx for _src_idx, corr_idx, _score in match_pairs}

        geometry_shifted = 0
        thickness_changed = 0
        for src_idx, corr_idx, _score in match_pairs:
            src_wall = source_walls[src_idx]
            corr_wall = corrected_walls[corr_idx]
            if self._wall_midpoint_distance(src_wall, corr_wall) > 8.0 or self._wall_length_ratio_delta(src_wall, corr_wall) > 0.12:
                geometry_shifted += 1
            src_thickness = float(src_wall.get("thickness", src_wall.get("thickness_px", 0.0)) or 0.0)
            corr_thickness = float(corr_wall.get("thickness", corr_wall.get("thickness_px", 0.0)) or 0.0)
            if abs(src_thickness - corr_thickness) > max(4.0, 0.15 * max(src_thickness, corr_thickness, 1.0)):
                thickness_changed += 1

        counts = {
            "missed": len(corrected_walls) - len(matched_corrected),
            "false_positive": len(source_walls) - len(matched_source),
            "merge": sum(1 for count in corrected_candidate_counts.values() if count > 1),
            "split": sum(1 for count in source_candidate_counts.values() if count > 1),
            "wrong_class": 0,
            "wrong_wall_link": 0,
            "geometry_shifted": geometry_shifted,
            "thickness_changed": thickness_changed,
        }
        hardness_score = (
            counts["missed"] * 3.0
            + counts["false_positive"] * 2.0
            + counts["merge"] * 2.0
            + counts["split"] * 2.0
            + counts["geometry_shifted"] * 1.0
            + counts["thickness_changed"] * 1.0
        )
        return {
            "step": "walls",
            "counts": counts,
            "matched_pairs": [
                {
                    "source_index": src_idx,
                    "corrected_index": corr_idx,
                    "score": score,
                }
                for src_idx, corr_idx, score in match_pairs
            ],
            "changed": any(value > 0 for value in counts.values()),
            "hardness_score": hardness_score,
        }

    def _build_openings_diff_summary(self, source_snapshot: dict[str, Any], corrected_snapshot: dict[str, Any]) -> dict[str, Any]:
        source_openings = self._snapshot_openings(source_snapshot)
        corrected_openings = self._snapshot_openings(corrected_snapshot)
        match_pairs, source_candidate_counts, corrected_candidate_counts = self._match_openings(source_openings, corrected_openings, with_candidate_counts=True)
        matched_source = {src_idx for src_idx, _corr_idx, _score in match_pairs}
        matched_corrected = {corr_idx for _src_idx, corr_idx, _score in match_pairs}

        wrong_class = 0
        wrong_wall_link = 0
        geometry_shifted = 0
        for src_idx, corr_idx, score in match_pairs:
            source_item = source_openings[src_idx]
            corrected_item = corrected_openings[corr_idx]
            if source_item["type"] != corrected_item["type"]:
                wrong_class += 1
            if source_item.get("wall_id") != corrected_item.get("wall_id"):
                wrong_wall_link += 1
            if score < 0.5:
                geometry_shifted += 1

        counts = {
            "missed": len(corrected_openings) - len(matched_corrected),
            "false_positive": len(source_openings) - len(matched_source),
            "merge": sum(1 for count in corrected_candidate_counts.values() if count > 1),
            "split": sum(1 for count in source_candidate_counts.values() if count > 1),
            "wrong_class": wrong_class,
            "wrong_wall_link": wrong_wall_link,
            "geometry_shifted": geometry_shifted,
        }
        hardness_score = (
            counts["missed"] * 3.0
            + counts["false_positive"] * 2.5
            + counts["merge"] * 2.0
            + counts["split"] * 2.0
            + counts["wrong_class"] * 1.5
            + counts["wrong_wall_link"] * 1.5
            + counts["geometry_shifted"] * 1.0
        )
        return {
            "step": "openings",
            "counts": counts,
            "matched_pairs": [
                {
                    "source_index": src_idx,
                    "corrected_index": corr_idx,
                    "score": score,
                }
                for src_idx, corr_idx, score in match_pairs
            ],
            "changed": any(value > 0 for value in counts.values()),
            "hardness_score": hardness_score,
        }

    def _match_walls(
        self,
        source_walls: list[dict[str, Any]],
        corrected_walls: list[dict[str, Any]],
    ) -> tuple[list[tuple[int, int, float]], dict[int, int], dict[int, int]]:
        candidates: list[tuple[int, int, float]] = []
        source_counts: dict[int, int] = {}
        corrected_counts: dict[int, int] = {}
        for src_idx, source_wall in enumerate(source_walls):
            for corr_idx, corrected_wall in enumerate(corrected_walls):
                score = self._wall_match_score(source_wall, corrected_wall)
                if score is None:
                    continue
                candidates.append((src_idx, corr_idx, score))
                source_counts[src_idx] = source_counts.get(src_idx, 0) + 1
                corrected_counts[corr_idx] = corrected_counts.get(corr_idx, 0) + 1
        matches: list[tuple[int, int, float]] = []
        used_source: set[int] = set()
        used_corrected: set[int] = set()
        for src_idx, corr_idx, score in sorted(candidates, key=lambda item: item[2]):
            if src_idx in used_source or corr_idx in used_corrected:
                continue
            used_source.add(src_idx)
            used_corrected.add(corr_idx)
            matches.append((src_idx, corr_idx, score))
        return matches, source_counts, corrected_counts

    def _match_openings(
        self,
        source_openings: list[dict[str, Any]],
        corrected_openings: list[dict[str, Any]],
        *,
        with_candidate_counts: bool = False,
    ):
        candidates: list[tuple[int, int, float]] = []
        source_counts: dict[int, int] = {}
        corrected_counts: dict[int, int] = {}
        for src_idx, source_item in enumerate(source_openings):
            for corr_idx, corrected_item in enumerate(corrected_openings):
                score = self._opening_match_score(source_item["bbox"], corrected_item["bbox"])
                if score is None:
                    continue
                candidates.append((src_idx, corr_idx, score))
                source_counts[src_idx] = source_counts.get(src_idx, 0) + 1
                corrected_counts[corr_idx] = corrected_counts.get(corr_idx, 0) + 1
        matches: list[tuple[int, int, float]] = []
        used_source: set[int] = set()
        used_corrected: set[int] = set()
        for src_idx, corr_idx, score in sorted(candidates, key=lambda item: item[2], reverse=True):
            if src_idx in used_source or corr_idx in used_corrected:
                continue
            used_source.add(src_idx)
            used_corrected.add(corr_idx)
            matches.append((src_idx, corr_idx, score))
        if with_candidate_counts:
            return matches, source_counts, corrected_counts
        return matches

    @staticmethod
    def _snapshot_openings(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        if snapshot.get("openings") is not None:
            return [RecognitionTrainingFeedbackService._normalize_opening_dict(item) for item in (snapshot.get("openings") or [])]
        items = []
        for door in snapshot.get("doors") or []:
            items.append(RecognitionTrainingFeedbackService._normalize_opening_dict({"type": "door", **door}))
        for window in snapshot.get("windows") or []:
            items.append(RecognitionTrainingFeedbackService._normalize_opening_dict({"type": "window", **window}))
        return items

    @staticmethod
    def _normalize_opening_dict(item: dict[str, Any]) -> dict[str, Any]:
        if item.get("bbox") is not None:
            bbox = [float(value) for value in item["bbox"]]
        else:
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
            width = float(item.get("width", 0.0))
            height = float(item.get("height", 0.0))
            bbox = [x, y, x + width, y + height]
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "wall_id": item.get("wall_id"),
            "rotation_deg": item.get("rotation_deg", 0.0),
            "bbox": bbox,
        }

    @staticmethod
    def _serialize_wall(wall) -> dict[str, Any]:
        return {
            "id": wall.id,
            "x1": float(wall.x1),
            "y1": float(wall.y1),
            "x2": float(wall.x2),
            "y2": float(wall.y2),
            "thickness": float(wall.thickness or 0.0),
            "alignment": wall.alignment or "center",
            "length_m": wall.length_m,
            "length_source": wall.length_source,
        }

    @staticmethod
    def _serialize_dimension(dimension) -> dict[str, Any]:
        return {
            "id": dimension.id,
            "x": float(dimension.x),
            "y": float(dimension.y),
            "value": float(dimension.value),
            "unit": dimension.unit,
            "text": dimension.text,
            "wall_id": dimension.wall_id,
            "room_id": dimension.room_id,
            "line_x1": dimension.line_x1,
            "line_y1": dimension.line_y1,
            "line_x2": dimension.line_x2,
            "line_y2": dimension.line_y2,
        }

    @staticmethod
    def _serialize_door(door) -> dict[str, Any]:
        return {
            "id": door.id,
            "type": "door",
            "x": float(door.x),
            "y": float(door.y),
            "width": float(door.width),
            "height": float(door.height),
            "wall_id": door.wall_id,
            "rotation_deg": float(door.rotation_deg or 0.0),
            "bbox": [
                float(door.x),
                float(door.y),
                float(door.x + door.width),
                float(door.y + door.height),
            ],
        }

    @staticmethod
    def _serialize_window(window) -> dict[str, Any]:
        return {
            "id": window.id,
            "type": "window",
            "x": float(window.x),
            "y": float(window.y),
            "width": float(window.width),
            "height": float(window.height),
            "wall_id": window.wall_id,
            "rotation_deg": float(window.rotation_deg or 0.0),
            "bbox": [
                float(window.x),
                float(window.y),
                float(window.x + window.width),
                float(window.y + window.height),
            ],
        }

    @staticmethod
    def _count_examples_by_status(examples: list[RecognitionFeedbackExample]) -> dict[str, int]:
        counts = {
            "approved": 0,
            "batched": 0,
            "exported": 0,
            "used": 0,
            "total": len(examples),
        }
        for example in examples:
            status = str(example.status or "").lower()
            if status in counts:
                counts[status] += 1
        return counts

    @staticmethod
    def _step_thresholds(step: str) -> dict[str, Any]:
        if step == "walls":
            return {
                "approved_examples": WALL_BATCH_MIN_APPROVED,
                "minimum_hard_examples": WALL_BATCH_MIN_HARD,
                "minimum_labeled_openings": None,
                "max_idle_days": MAX_IDLE_DAYS,
                "minimum_real_correction_ratio": MIN_REAL_CORRECTION_RATIO,
            }
        return {
            "approved_examples": OPENINGS_BATCH_MIN_APPROVED,
            "minimum_hard_examples": None,
            "minimum_labeled_openings": OPENINGS_BATCH_MIN_LABELED,
            "max_idle_days": MAX_IDLE_DAYS,
            "minimum_real_correction_ratio": MIN_REAL_CORRECTION_RATIO,
        }

    @staticmethod
    def _dataset_split(floor_plan_id: int) -> str:
        hash_value = hashlib.sha1(str(floor_plan_id).encode("utf-8")).hexdigest()
        bucket = int(hash_value[:8], 16) % 100
        if bucket < 80:
            return "train"
        if bucket < 90:
            return "val"
        return "test"

    @staticmethod
    def _count_splits(entries: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"train": 0, "val": 0, "test": 0}
        for entry in entries:
            split = entry.get("split")
            if split in counts:
                counts[split] += 1
        return counts

    @staticmethod
    def _wall_angle_deg(wall: dict[str, Any] | None) -> float:
        if not wall:
            return 0.0
        return math.degrees(math.atan2(float(wall["y2"]) - float(wall["y1"]), float(wall["x2"]) - float(wall["x1"])))

    @staticmethod
    def _wall_match_score(source_wall: dict[str, Any], corrected_wall: dict[str, Any]) -> float | None:
        angle_diff = RecognitionTrainingFeedbackService._wall_angle_difference(source_wall, corrected_wall)
        if angle_diff > 12.0:
            return None
        midpoint_distance = RecognitionTrainingFeedbackService._wall_midpoint_distance(source_wall, corrected_wall)
        length_ratio_delta = RecognitionTrainingFeedbackService._wall_length_ratio_delta(source_wall, corrected_wall)
        if midpoint_distance > 80.0 or length_ratio_delta > 0.5:
            return None
        thickness_delta = abs(
            float(source_wall.get("thickness", source_wall.get("thickness_px", 0.0)) or 0.0)
            - float(corrected_wall.get("thickness", corrected_wall.get("thickness_px", 0.0)) or 0.0)
        )
        return midpoint_distance + (length_ratio_delta * 100.0) + thickness_delta * 0.05

    @staticmethod
    def _wall_angle_difference(source_wall: dict[str, Any], corrected_wall: dict[str, Any]) -> float:
        angle_a = RecognitionTrainingFeedbackService._wall_angle_deg(source_wall) % 180.0
        angle_b = RecognitionTrainingFeedbackService._wall_angle_deg(corrected_wall) % 180.0
        diff = abs(angle_a - angle_b)
        return min(diff, 180.0 - diff)

    @staticmethod
    def _wall_midpoint_distance(source_wall: dict[str, Any], corrected_wall: dict[str, Any]) -> float:
        sx = (float(source_wall["x1"]) + float(source_wall["x2"])) / 2.0
        sy = (float(source_wall["y1"]) + float(source_wall["y2"])) / 2.0
        cx = (float(corrected_wall["x1"]) + float(corrected_wall["x2"])) / 2.0
        cy = (float(corrected_wall["y1"]) + float(corrected_wall["y2"])) / 2.0
        return math.hypot(cx - sx, cy - sy)

    @staticmethod
    def _wall_length_ratio_delta(source_wall: dict[str, Any], corrected_wall: dict[str, Any]) -> float:
        source_length = math.hypot(float(source_wall["x2"]) - float(source_wall["x1"]), float(source_wall["y2"]) - float(source_wall["y1"]))
        corrected_length = math.hypot(float(corrected_wall["x2"]) - float(corrected_wall["x1"]), float(corrected_wall["y2"]) - float(corrected_wall["y1"]))
        if source_length < 1e-6 and corrected_length < 1e-6:
            return 0.0
        return abs(source_length - corrected_length) / max(source_length, corrected_length, 1.0)

    @staticmethod
    def _opening_match_score(source_bbox: list[float], corrected_bbox: list[float]) -> float | None:
        iou = RecognitionTrainingFeedbackService._bbox_iou(source_bbox, corrected_bbox)
        if iou >= 0.15:
            return iou
        source_center = ((source_bbox[0] + source_bbox[2]) / 2.0, (source_bbox[1] + source_bbox[3]) / 2.0)
        corrected_center = ((corrected_bbox[0] + corrected_bbox[2]) / 2.0, (corrected_bbox[1] + corrected_bbox[3]) / 2.0)
        if math.hypot(corrected_center[0] - source_center[0], corrected_center[1] - source_center[1]) <= 24.0:
            return 0.15
        return None

    @staticmethod
    def _bbox_iou(box_a: list[float], box_b: list[float]) -> float:
        x1 = max(float(box_a[0]), float(box_b[0]))
        y1 = max(float(box_a[1]), float(box_b[1]))
        x2 = min(float(box_a[2]), float(box_b[2]))
        y2 = min(float(box_a[3]), float(box_b[3]))
        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter = inter_w * inter_h
        area_a = max(0.0, float(box_a[2]) - float(box_a[0])) * max(0.0, float(box_a[3]) - float(box_a[1]))
        area_b = max(0.0, float(box_b[2]) - float(box_b[0])) * max(0.0, float(box_b[3]) - float(box_b[1]))
        union = area_a + area_b - inter
        if union <= 1e-6:
            return 0.0
        return inter / union

    @staticmethod
    def _is_idle_due(last_batch: RecognitionTrainingBatch | None) -> bool:
        if last_batch is None:
            return True
        last_exported = _coerce_utc_datetime(last_batch.exported_at or last_batch.created_at)
        if last_exported is None:
            return True
        return datetime.now(timezone.utc) - last_exported >= timedelta(days=MAX_IDLE_DAYS)

    def _get_floor_plan(self, floor_plan_id: int) -> FloorPlan:
        floor_plan = self.db.query(FloorPlan).filter(FloorPlan.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _ensure_supported_step(step: str) -> None:
        if step not in SUPPORTED_FEEDBACK_STEPS:
            raise AppError(400, "unsupported_feedback_step", f"Unsupported feedback step: {step}")

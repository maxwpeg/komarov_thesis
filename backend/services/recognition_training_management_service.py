"""Recognition training management, curation, and run orchestration."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from sqlalchemy.orm import Session, joinedload

from backend.config import settings
from backend.errors import AppError
from backend.models import (
    FloorPlan,
    RecognitionActiveModel,
    RecognitionFeedbackExample,
    RecognitionTrainingBatch,
    RecognitionTrainingBatchExample,
    RecognitionTrainingRun,
)
from backend.services.recognition_training_feedback_service import (
    DETECTOR_VERSION,
    SUPPORTED_FEEDBACK_STEPS,
    TRAINING_PARAMETER_DEFAULTS,
    RecognitionTrainingFeedbackService,
    UTC_MIN_DATETIME,
    _coerce_utc_datetime,
)


ACTIVE_TRAINING_RUN_STATUSES = ("queued", "running")
QUEUED_RUN_START_GRACE_SECONDS = 20


@dataclass(slots=True)
class RecognitionTrainingManagementService:
    """Management API for reusable feedback examples and asynchronous training runs."""

    db: Session
    storage: Any
    feedback_service: RecognitionTrainingFeedbackService = field(init=False)

    def __post_init__(self) -> None:
        self.feedback_service = RecognitionTrainingFeedbackService(self.db, self.storage)

    def get_overview(self) -> dict[str, Any]:
        self._reconcile_stale_active_runs()
        active_models = self._active_model_map_by_step()
        steps: list[dict[str, Any]] = []
        for step in SUPPORTED_FEEDBACK_STEPS:
            examples = (
                self.db.query(RecognitionFeedbackExample)
                .filter(RecognitionFeedbackExample.step == step)
                .all()
            )
            approved_count = sum(1 for item in examples if (item.curation_status or "approved") == "approved")
            excluded_count = sum(1 for item in examples if (item.curation_status or "approved") == "excluded")
            selected_examples, hint = self.feedback_service.select_examples_for_batch(step)
            thresholds = self.feedback_service.get_step_thresholds(step)
            last_batch = (
                self.db.query(RecognitionTrainingBatch)
                .filter(RecognitionTrainingBatch.step == step)
                .order_by(RecognitionTrainingBatch.exported_at.desc(), RecognitionTrainingBatch.created_at.desc())
                .first()
            )
            last_successful_run = (
                self.db.query(RecognitionTrainingRun)
                .filter(
                    RecognitionTrainingRun.step == step,
                    RecognitionTrainingRun.status == "succeeded",
                )
                .order_by(RecognitionTrainingRun.finished_at.desc(), RecognitionTrainingRun.requested_at.desc())
                .first()
            )
            steps.append(
                {
                    "step": step,
                    "detector_version": DETECTOR_VERSION,
                    "approved_examples": approved_count,
                    "excluded_examples": excluded_count,
                    "selected_for_batch": len(selected_examples),
                    "recommended_batch_size": int(thresholds.get("approved_examples") or 0),
                    "thresholds": thresholds,
                    "next_batch_hint": hint,
                    "last_batch": last_batch.to_dict() if last_batch is not None else None,
                    "last_successful_run": self._serialize_run(last_successful_run, active_models=active_models) if last_successful_run is not None else None,
                    "active_model": self._serialize_active_model(active_models.get(step)),
                    "training_defaults": self._training_defaults(step),
                }
            )
        return {
            "detector_version": DETECTOR_VERSION,
            "steps": steps,
        }

    def list_examples(
        self,
        *,
        step: str | None = None,
        curation_status: str | None = None,
        project_id: int | None = None,
        floor_plan_id: int | None = None,
        changed_only: bool = False,
        search: str | None = None,
        sort_by: str = "submitted_at",
        sort_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        query = (
            self.db.query(RecognitionFeedbackExample)
            .options(
                joinedload(RecognitionFeedbackExample.floor_plan).joinedload(FloorPlan.project),
                joinedload(RecognitionFeedbackExample.batch_links)
                .joinedload(RecognitionTrainingBatchExample.training_batch)
                .joinedload(RecognitionTrainingBatch.training_runs),
            )
            .order_by(RecognitionFeedbackExample.submitted_at.desc(), RecognitionFeedbackExample.id.desc())
        )
        if step:
            self.feedback_service._ensure_supported_step(step)
            query = query.filter(RecognitionFeedbackExample.step == step)
        if curation_status:
            query = query.filter(RecognitionFeedbackExample.curation_status == curation_status)
        if project_id is not None:
            query = query.join(RecognitionFeedbackExample.floor_plan).filter(FloorPlan.project_id == project_id)
        if floor_plan_id is not None:
            query = query.filter(RecognitionFeedbackExample.floor_plan_id == floor_plan_id)

        examples = query.all()
        items = [self._serialize_example_summary(item) for item in examples]
        if changed_only:
            items = [item for item in items if item["changed"]]
        if search:
            needle = search.strip().lower()
            items = [
                item
                for item in items
                if needle in " ".join(
                    str(value).lower()
                    for value in (
                        item["project_name"],
                        item["project_code"],
                        item["floor_plan_name"],
                        item["floor_number"],
                        item["notes"],
                        " ".join(item["issue_tags"]),
                    )
                )
            ]

        reverse = str(sort_dir or "desc").lower() != "asc"
        if sort_by == "hardness":
            items.sort(key=lambda item: (float(item["hardness_score"] or 0.0), item["id"]), reverse=reverse)
        else:
            items.sort(key=lambda item: (item["submitted_at"] or "", item["id"]), reverse=reverse)
        return items

    def get_example_detail(self, example_id: int) -> dict[str, Any]:
        example = (
            self.db.query(RecognitionFeedbackExample)
            .options(
                joinedload(RecognitionFeedbackExample.floor_plan).joinedload(FloorPlan.project),
                joinedload(RecognitionFeedbackExample.batch_links)
                .joinedload(RecognitionTrainingBatchExample.training_batch)
                .joinedload(RecognitionTrainingBatch.training_runs),
            )
            .filter(RecognitionFeedbackExample.id == example_id)
            .first()
        )
        if example is None:
            raise AppError(404, "recognition_training_example_not_found", "Training example not found")

        detail = self._serialize_example_summary(example)
        detail.update(
            {
                "step_revision": example.step_revision,
                "detector_version": example.detector_version,
                "source_snapshot": example.source_snapshot,
                "corrected_snapshot": example.corrected_snapshot,
                "diff_summary": example.diff_summary,
                "original_image_path": example.floor_plan.original_image_path if example.floor_plan is not None else None,
                "batches": [],
                "runs": [],
            }
        )
        batch_items: list[dict[str, Any]] = []
        runs: dict[str, dict[str, Any]] = {}
        active_models = self._active_model_map_by_step()
        for link in sorted(
            example.batch_links,
            key=lambda item: _coerce_utc_datetime(item.included_at) or UTC_MIN_DATETIME,
            reverse=True,
        ):
            batch = link.training_batch
            if batch is None:
                continue
            batch_items.append(
                {
                    "included_at": link.included_at.isoformat() if link.included_at else None,
                    **batch.to_dict(),
                }
            )
            for run in batch.training_runs:
                runs[run.run_id] = self._serialize_run(run, active_models=active_models)
        detail["batches"] = batch_items
        detail["runs"] = sorted(
            runs.values(),
            key=lambda item: item.get("requested_at") or "",
            reverse=True,
        )
        return detail

    def update_example(
        self,
        example_id: int,
        *,
        curation_status: str | None = None,
        issue_tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        example = self._get_example(example_id)
        now = datetime.now(timezone.utc)
        if curation_status is not None:
            normalized_status = str(curation_status).strip().lower()
            if normalized_status not in {"approved", "excluded"}:
                raise AppError(400, "recognition_training_invalid_curation_status", "Unsupported curation status")
            example.curation_status = normalized_status
            example.curated_at = now
        if issue_tags is not None:
            example.issue_tags = [str(tag).strip() for tag in issue_tags if str(tag).strip()]
        if notes is not None:
            example.notes = (notes or "").strip() or None
        self.db.commit()
        return self.get_example_detail(example_id)

    def bulk_curate(self, example_ids: list[int], *, curation_status: str) -> dict[str, Any]:
        normalized_status = str(curation_status).strip().lower()
        if normalized_status not in {"approved", "excluded"}:
            raise AppError(400, "recognition_training_invalid_curation_status", "Unsupported curation status")
        ids = sorted({int(item) for item in example_ids if int(item) > 0})
        if not ids:
            raise AppError(400, "recognition_training_empty_selection", "Select at least one example")
        examples = (
            self.db.query(RecognitionFeedbackExample)
            .filter(RecognitionFeedbackExample.id.in_(ids))
            .all()
        )
        now = datetime.now(timezone.utc)
        for example in examples:
            example.curation_status = normalized_status
            example.curated_at = now
        self.db.commit()
        return {
            "updated_count": len(examples),
            "curation_status": normalized_status,
        }

    def list_runs(self) -> list[dict[str, Any]]:
        self._reconcile_stale_active_runs()
        active_models = self._active_model_map_by_step()
        runs = (
            self.db.query(RecognitionTrainingRun)
            .options(joinedload(RecognitionTrainingRun.training_batch))
            .order_by(RecognitionTrainingRun.requested_at.desc(), RecognitionTrainingRun.id.desc())
            .all()
        )
        return [self._serialize_run(run, active_models=active_models) for run in runs]

    def get_run(self, run_id: str) -> dict[str, Any]:
        self._reconcile_stale_active_runs()
        return self._serialize_run(self._get_run_model(run_id), active_models=self._active_model_map_by_step())

    def list_active_models(self) -> list[dict[str, Any]]:
        return [
            self._serialize_active_model(item)
            for item in sorted(self._list_active_model_records(), key=lambda model: model.step)
        ]

    def get_run_log(self, run_id: str, *, tail: int = 200) -> dict[str, Any]:
        run = self._get_run_model(run_id)
        log_path = Path(run.log_path) if run.log_path else None
        if log_path is None or not log_path.exists():
            return {
                "run_id": run_id,
                "log_path": str(log_path) if log_path else None,
                "content": "",
            }
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return {
            "run_id": run_id,
            "log_path": str(log_path),
            "content": "\n".join(lines[-max(int(tail), 1):]),
        }

    def activate_run(self, run_id: str) -> dict[str, Any]:
        run = self._get_run_model(run_id)
        if run.status != "succeeded":
            raise AppError(
                409,
                "recognition_training_run_not_activatable",
                f"Training run {run.run_id} is not completed successfully",
            )

        artifacts = self._collect_run_artifacts(run)
        best_checkpoint_path = artifacts["best_checkpoint_path"]
        if not best_checkpoint_path:
            raise AppError(
                409,
                "recognition_training_checkpoint_missing",
                f"Training run {run.run_id} does not have a best.pt checkpoint",
            )

        active = (
            self.db.query(RecognitionActiveModel)
            .filter(RecognitionActiveModel.step == run.step)
            .first()
        )
        now = datetime.now(timezone.utc)
        if active is None:
            active = RecognitionActiveModel(
                step=run.step,
                training_run_id=run.id,
                artifact_path=best_checkpoint_path,
                activated_at=now,
                config_snapshot=run.config or {},
                metrics_summary=run.metrics_summary or {},
            )
            self.db.add(active)
        else:
            active.training_run_id = run.id
            active.artifact_path = best_checkpoint_path
            active.activated_at = now
            active.config_snapshot = run.config or {}
            active.metrics_summary = run.metrics_summary or {}
        self.db.commit()
        self.db.refresh(active)
        return self._serialize_active_model(active)

    def create_run(
        self,
        *,
        step: str,
        epochs: int | None = None,
        imgsz: int | None = None,
        batch: int | None = None,
        patience: int | None = None,
        force: bool = False,
        spawn_process: bool = True,
    ) -> dict[str, Any]:
        self.feedback_service._ensure_supported_step(step)
        self._reconcile_stale_active_runs()
        active = self._find_active_run()
        if active is not None:
            raise AppError(
                409,
                "recognition_training_run_active",
                f"Training run {active.run_id} is already active",
            )

        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{step}"
        batch_export = self.feedback_service.export_feedback_batch(
            step,
            batch_id=run_id,
            commit=False,
            force=force,
        )
        if batch_export["batch"] is None:
            skipped = batch_export["skipped"] or {}
            raise AppError(
                409,
                "recognition_training_batch_not_ready",
                f"Could not build training batch for {step}: {skipped.get('reason', 'not_ready')}",
            )

        batch_model = (
            self.db.query(RecognitionTrainingBatch)
            .filter(RecognitionTrainingBatch.id == int(batch_export["batch"]["id"]))
            .first()
        )
        if batch_model is None:
            raise AppError(500, "recognition_training_batch_missing", "Training batch was not persisted")

        artifact_dir = (settings.outputs_dir / "recognition_training" / run_id).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        log_path = artifact_dir / "stdout.log"
        log_path.touch(exist_ok=True)
        run = RecognitionTrainingRun(
            run_id=run_id,
            training_batch_id=batch_model.id,
            step=step,
            status="queued",
            config={
                **self._training_config(
                    step,
                    epochs=epochs,
                    imgsz=imgsz,
                    batch=batch,
                    patience=patience,
                ),
                "force": bool(force),
            },
            artifact_dir=str(artifact_dir),
            log_path=str(log_path),
            requested_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.commit()

        if spawn_process:
            try:
                self._spawn_training_process(run_id, log_path)
            except Exception as exc:  # pragma: no cover - exercised through service tests
                run.status = "failed"
                run.error_message = str(exc)
                run.finished_at = datetime.now(timezone.utc)
                batch_model.status = "failed"
                self.db.commit()
                raise AppError(500, "recognition_training_spawn_failed", f"Failed to start training process: {exc}") from exc

        return self.get_run(run_id)

    def run_training_job(self, run_id: str) -> dict[str, Any]:
        run = self._get_run_model(run_id)
        batch = run.training_batch
        if batch is None:
            raise AppError(404, "recognition_training_batch_not_found", "Training batch not found")

        artifact_dir = Path(run.artifact_dir or (settings.outputs_dir / "recognition_training" / run_id)).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        run.artifact_dir = str(artifact_dir)
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        batch.status = "running"
        self.db.commit()

        try:
            dataset_summary = self._build_yolo_dataset(run, artifact_dir / "dataset")
            params_payload = {
                "run_id": run.run_id,
                "step": run.step,
                "config": run.config or {},
                "batch": batch.to_dict(),
                "dataset": dataset_summary,
            }
            (artifact_dir / "params.json").write_text(json.dumps(params_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            if os.getenv("RECOGNITION_TRAINING_FAKE_RUN") == "1":
                metrics = self._complete_fake_run(run, artifact_dir, dataset_summary)
            else:
                metrics = self._run_ultralytics_training(run, artifact_dir, dataset_summary)

            finished_at = datetime.now(timezone.utc)
            run.status = "succeeded"
            run.metrics_summary = metrics
            run.finished_at = finished_at
            batch.status = "succeeded"
            batch.summary = {
                **(batch.summary or {}),
                "dataset_dir": str((artifact_dir / "dataset").resolve()),
                "training_run_id": run.run_id,
                "metrics_summary": metrics,
            }
            for link in batch.example_links:
                example = link.feedback_example
                if example is None:
                    continue
                example.used_at = finished_at
                example.status = "used"
            (artifact_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            self.db.commit()
            return self.get_run(run_id)
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            batch.status = "failed"
            self.db.commit()
            raise

    def _build_yolo_dataset(self, run: RecognitionTrainingRun, dataset_dir: Path) -> dict[str, Any]:
        batch = run.training_batch
        if batch is None or not batch.export_dir:
            raise AppError(400, "recognition_training_export_missing", "Exported batch assets are unavailable")

        batch_dir = Path(batch.export_dir)
        manifest_path = Path((batch.summary or {}).get("manifest_path") or (batch_dir / "manifest.jsonl"))
        if not manifest_path.exists():
            raise AppError(400, "recognition_training_manifest_missing", f"Manifest is missing for batch {batch.batch_id}")

        dataset_dir.mkdir(parents=True, exist_ok=True)
        image_dirs = {split: dataset_dir / "images" / split for split in ("train", "val", "test")}
        label_dirs = {split: dataset_dir / "labels" / split for split in ("train", "val", "test")}
        for path in [*image_dirs.values(), *label_dirs.values()]:
            path.mkdir(parents=True, exist_ok=True)

        entries = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        split_assignments = self._resolve_dataset_split_assignments(entries)
        split_counts = {"train": 0, "val": 0, "test": 0}
        for index, entry in enumerate(entries):
            image_source = batch_dir / entry["image_path"]
            if not image_source.exists():
                raise AppError(400, "recognition_training_image_missing", f"Missing exported image {image_source}")
            dataset_image_name = f"{image_source.stem}.png"

            corrected_snapshot_path = batch_dir / entry["corrected_snapshot_path"]
            corrected_snapshot = json.loads(corrected_snapshot_path.read_text(encoding="utf-8"))
            label_lines = self._build_label_lines(
                run.step,
                corrected_snapshot,
            )
            for split in split_assignments[index]:
                image_target = image_dirs[split] / dataset_image_name
                self._materialize_training_image(image_source, image_target)
                label_target = label_dirs[split] / f"{image_target.stem}.txt"
                label_target.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")
                split_counts[split] += 1

        names = {0: "wall"} if run.step == "walls" else {0: "door", 1: "window"}
        dataset_yaml = dataset_dir / "dataset.yaml"
        dataset_yaml.write_text(
            "\n".join(
                [
                    f"path: {dataset_dir.as_posix()}",
                    "train: images/train",
                    "val: images/val",
                    "test: images/test",
                    f"names: {json.dumps(names, ensure_ascii=False)}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "dataset_dir": str(dataset_dir),
            "data_yaml": str(dataset_yaml),
            "split_counts": split_counts,
            "class_names": names,
            "sample_count": len(entries),
            "dataset_item_count": sum(split_counts.values()),
        }

    @staticmethod
    def _resolve_dataset_split_assignments(entries: list[dict[str, Any]]) -> list[list[str]]:
        if not entries:
            return []

        requested_assignments = [[str(entry.get("split") or "train")] for entry in entries]
        requested_counts = {"train": 0, "val": 0, "test": 0}
        for assignment in requested_assignments:
            split = assignment[0]
            if split in requested_counts:
                requested_counts[split] += 1

        if requested_counts["train"] > 0 and requested_counts["val"] > 0:
            return requested_assignments

        ordered_indices = sorted(
            range(len(entries)),
            key=lambda index: (
                int(entries[index].get("floor_plan_id") or 0),
                int(entries[index].get("sample_id") or 0),
                index,
            ),
        )
        count = len(ordered_indices)
        assignments: list[list[str]] = [[] for _ in entries]

        if count == 1:
            assignments[ordered_indices[0]] = ["train", "val"]
            return assignments

        if count < 5:
            val_count = 1
            test_count = 0
        elif count < 10:
            val_count = 1
            test_count = 1
        else:
            val_count = max(1, int(round(count * 0.2)))
            test_count = max(1, int(round(count * 0.1)))

        train_count = count - val_count - test_count
        if train_count <= 0:
            test_count = max(0, count - 2)
            train_count = max(1, count - val_count - test_count)
        if train_count + val_count + test_count > count:
            overflow = train_count + val_count + test_count - count
            test_count = max(0, test_count - overflow)

        cursor = 0
        for _ in range(train_count):
            assignments[ordered_indices[cursor]] = ["train"]
            cursor += 1
        for _ in range(val_count):
            assignments[ordered_indices[cursor]] = ["val"]
            cursor += 1
        while cursor < count:
            assignments[ordered_indices[cursor]] = ["test"]
            cursor += 1

        if not any("val" in item for item in assignments):
            assignments[ordered_indices[-1]] = ["val"]
        if not any("train" in item for item in assignments):
            assignments[ordered_indices[0]] = ["train", *[split for split in assignments[ordered_indices[0]] if split != "train"]]
        return assignments

    @staticmethod
    def _materialize_training_image(source_path: Path, target_path: Path) -> None:
        try:
            with Image.open(source_path) as image:
                normalized = ImageOps.exif_transpose(image)
                if normalized.mode not in {"RGB", "L"}:
                    normalized = normalized.convert("RGB")
                elif normalized.mode == "L":
                    normalized = normalized.convert("RGB")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                normalized.save(target_path, format="PNG")
        except Exception as exc:
            raise AppError(
                400,
                "recognition_training_image_decode_failed",
                f"Could not convert training image {source_path} to PNG: {exc}",
            ) from exc

    def _build_label_lines(self, step: str, corrected_snapshot: dict[str, Any]) -> list[str]:
        image_meta = corrected_snapshot.get("image") or {}
        width = max(int(image_meta.get("width") or 0), 1)
        height = max(int(image_meta.get("height") or 0), 1)
        if step == "walls":
            scale_factor = float(image_meta.get("scale_factor") or 1.0 or 1.0)
            lines = []
            for wall in corrected_snapshot.get("walls") or []:
                points = self._wall_polygon(wall, width=width, height=height, scale_factor=scale_factor)
                lines.append(self._polygon_to_label_line(0, points, width=width, height=height))
            return lines

        lines = []
        for opening in self.feedback_service._snapshot_openings(corrected_snapshot):
            class_id = 0 if opening.get("type") == "door" else 1
            bbox = opening.get("bbox") or [0, 0, 0, 0]
            points = [
                (float(bbox[0]), float(bbox[1])),
                (float(bbox[2]), float(bbox[1])),
                (float(bbox[2]), float(bbox[3])),
                (float(bbox[0]), float(bbox[3])),
            ]
            lines.append(self._polygon_to_label_line(class_id, points, width=width, height=height))
        return lines

    def _complete_fake_run(self, run: RecognitionTrainingRun, artifact_dir: Path, dataset_summary: dict[str, Any]) -> dict[str, Any]:
        (artifact_dir / "best.pt").write_bytes(b"fake-best")
        (artifact_dir / "last.pt").write_bytes(b"fake-last")
        return {
            "mode": "fake",
            "step": run.step,
            "sample_count": dataset_summary["sample_count"],
            "dataset_item_count": dataset_summary["dataset_item_count"],
            "split_counts": dataset_summary["split_counts"],
            "fitness": 1.0,
        }

    def _run_ultralytics_training(self, run: RecognitionTrainingRun, artifact_dir: Path, dataset_summary: dict[str, Any]) -> dict[str, Any]:
        from ultralytics import YOLO

        config = run.config or {}
        model_path = (settings.project_root / str(config.get("model") or self._training_defaults(run.step)["model"])).resolve()
        if not model_path.exists():
            raise AppError(400, "recognition_training_model_missing", f"Base model not found: {model_path}")
        resolved_device, resolution_reason = self._resolve_ultralytics_device_details(
            config.get("device", self._training_defaults(run.step)["device"])
        )
        print(
            f"[recognition-training] device requested={config.get('device', self._training_defaults(run.step)['device'])!r} "
            f"resolved={resolved_device!r} reason={resolution_reason}",
            flush=True,
        )

        trainer_root = artifact_dir / "ultralytics"
        trainer_root.mkdir(parents=True, exist_ok=True)
        results = YOLO(str(model_path)).train(
            data=str(Path(dataset_summary["data_yaml"]).resolve()),
            epochs=int(config.get("epochs", self._training_defaults(run.step)["epochs"])),
            imgsz=int(config.get("imgsz", self._training_defaults(run.step)["imgsz"])),
            batch=int(config.get("batch", self._training_defaults(run.step)["batch"])),
            patience=int(config.get("patience", self._training_defaults(run.step)["patience"])),
            device=resolved_device,
            project=str(trainer_root),
            name="run",
            exist_ok=True,
            verbose=True,
            task="segment",
        )
        save_dir = Path(getattr(results, "save_dir", trainer_root / "run"))
        weights_dir = save_dir / "weights"
        for filename in ("best.pt", "last.pt"):
            source = weights_dir / filename
            if source.exists():
                shutil.copy2(source, artifact_dir / filename)
        metrics = {
            "mode": "ultralytics",
            "step": run.step,
            "sample_count": dataset_summary["sample_count"],
            "dataset_item_count": dataset_summary["dataset_item_count"],
            "split_counts": dataset_summary["split_counts"],
            "requested_device": str(config.get("device", self._training_defaults(run.step)["device"])),
            "resolved_device": resolved_device,
            "device_resolution_reason": resolution_reason,
            "results": {key: float(value) for key, value in getattr(results, "results_dict", {}).items()},
            "save_dir": str(save_dir),
        }
        return metrics

    def _spawn_training_process(self, run_id: str, log_path: Path) -> None:
        script_path = settings.project_root / "tools" / "run_recognition_training.py"
        if not script_path.exists():
            raise FileNotFoundError(script_path)
        env = os.environ.copy()
        project_root = str(settings.project_root.resolve())
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else project_root
        )
        with log_path.open("a", encoding="utf-8") as log_file:
            subprocess.Popen(
                [sys.executable, str(script_path), "--run-id", run_id],
                cwd=str(settings.project_root),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )

    def _serialize_example_summary(self, example: RecognitionFeedbackExample) -> dict[str, Any]:
        floor_plan = example.floor_plan
        project = floor_plan.project if floor_plan is not None else None
        used_run_ids = {
            run.run_id
            for link in example.batch_links
            for run in link.training_batch.training_runs
            if run.status == "succeeded"
        }
        return {
            "id": example.id,
            "step": example.step,
            "floor_plan_id": example.floor_plan_id,
            "floor_plan_name": floor_plan.name if floor_plan is not None else None,
            "floor_number": floor_plan.floor_number if floor_plan is not None else None,
            "project_id": project.id if project is not None else None,
            "project_name": project.facility if project is not None else None,
            "project_code": project.code if project is not None else None,
            "submitted_at": example.submitted_at.isoformat() if example.submitted_at else None,
            "hardness_score": float(example.hardness_score or 0.0),
            "changed": bool((example.diff_summary or {}).get("changed")),
            "issue_tags": example.issue_tags or [],
            "notes": example.notes,
            "curation_status": example.curation_status or "approved",
            "times_used": len(used_run_ids),
        }

    def _serialize_run(
        self,
        run: RecognitionTrainingRun,
        *,
        active_models: dict[str, RecognitionActiveModel] | None = None,
    ) -> dict[str, Any]:
        payload = run.to_dict()
        payload["batch"] = run.training_batch.to_dict() if run.training_batch is not None else None
        payload["artifacts"] = self._collect_run_artifacts(run)
        active_model = (active_models or {}).get(run.step)
        payload["is_active_for_step"] = bool(active_model is not None and active_model.training_run_id == run.id)
        return payload

    def _serialize_active_model(self, active_model: RecognitionActiveModel | None) -> dict[str, Any] | None:
        if active_model is None:
            return None
        run = active_model.training_run
        payload = active_model.to_dict()
        payload["run_id"] = run.run_id if run is not None else None
        return payload

    def _collect_run_artifacts(self, run: RecognitionTrainingRun) -> dict[str, Any]:
        artifact_dir = Path(run.artifact_dir) if run.artifact_dir else None
        best_checkpoint_path = None
        last_checkpoint_path = None
        metrics_json_path = None
        params_json_path = None
        if artifact_dir is not None:
            best_candidate = artifact_dir / "best.pt"
            last_candidate = artifact_dir / "last.pt"
            metrics_candidate = artifact_dir / "metrics.json"
            params_candidate = artifact_dir / "params.json"
            best_checkpoint_path = str(best_candidate) if best_candidate.exists() else None
            last_checkpoint_path = str(last_candidate) if last_candidate.exists() else None
            metrics_json_path = str(metrics_candidate) if metrics_candidate.exists() else None
            params_json_path = str(params_candidate) if params_candidate.exists() else None
        return {
            "best_checkpoint_path": best_checkpoint_path,
            "last_checkpoint_path": last_checkpoint_path,
            "metrics_json_path": metrics_json_path,
            "params_json_path": params_json_path,
            "has_best_checkpoint": bool(best_checkpoint_path),
            "has_last_checkpoint": bool(last_checkpoint_path),
        }

    def _list_active_model_records(self) -> list[RecognitionActiveModel]:
        return (
            self.db.query(RecognitionActiveModel)
            .options(joinedload(RecognitionActiveModel.training_run))
            .order_by(RecognitionActiveModel.step.asc(), RecognitionActiveModel.activated_at.desc())
            .all()
        )

    def _active_model_map_by_step(self) -> dict[str, RecognitionActiveModel]:
        active_by_step: dict[str, RecognitionActiveModel] = {}
        for item in self._list_active_model_records():
            active_by_step.setdefault(item.step, item)
        return active_by_step

    def _get_example(self, example_id: int) -> RecognitionFeedbackExample:
        example = self.db.query(RecognitionFeedbackExample).filter(RecognitionFeedbackExample.id == example_id).first()
        if example is None:
            raise AppError(404, "recognition_training_example_not_found", "Training example not found")
        return example

    def _get_run_model(self, run_id: str) -> RecognitionTrainingRun:
        run = (
            self.db.query(RecognitionTrainingRun)
            .options(
                joinedload(RecognitionTrainingRun.training_batch)
                .joinedload(RecognitionTrainingBatch.example_links)
                .joinedload(RecognitionTrainingBatchExample.feedback_example)
            )
            .filter(RecognitionTrainingRun.run_id == run_id)
            .first()
        )
        if run is None:
            raise AppError(404, "recognition_training_run_not_found", "Training run not found")
        return run

    def _find_active_run(self) -> RecognitionTrainingRun | None:
        return (
            self.db.query(RecognitionTrainingRun)
            .filter(RecognitionTrainingRun.status.in_(ACTIVE_TRAINING_RUN_STATUSES))
            .order_by(RecognitionTrainingRun.requested_at.asc(), RecognitionTrainingRun.id.asc())
            .first()
        )

    def _reconcile_stale_active_runs(self) -> None:
        now = datetime.now(timezone.utc)
        queued_cutoff = now - timedelta(seconds=QUEUED_RUN_START_GRACE_SECONDS)
        active_runs = (
            self.db.query(RecognitionTrainingRun)
            .options(joinedload(RecognitionTrainingRun.training_batch))
            .filter(RecognitionTrainingRun.status.in_(ACTIVE_TRAINING_RUN_STATUSES))
            .all()
        )
        changed = False
        for run in active_runs:
            if run.status != "queued":
                continue
            requested_at = _coerce_utc_datetime(run.requested_at) or now
            if requested_at > queued_cutoff:
                continue
            error_message = "Training runner did not start and remained queued beyond the startup grace period."
            log_path = Path(run.log_path) if run.log_path else None
            if log_path is not None and log_path.exists():
                log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:].strip()
                if log_tail:
                    last_line = next((line.strip() for line in reversed(log_tail.splitlines()) if line.strip()), "")
                    if last_line:
                        error_message = f"Training runner startup failed: {last_line}"
                    elif "Traceback" in log_tail:
                        error_message = "Training runner startup failed. See stdout.log for traceback."
            run.status = "failed"
            run.error_message = error_message
            run.finished_at = now
            if run.training_batch is not None:
                run.training_batch.status = "failed"
            changed = True
        if changed:
            self.db.commit()

    @staticmethod
    def _training_defaults(step: str) -> dict[str, Any]:
        return dict(TRAINING_PARAMETER_DEFAULTS[step])

    def _training_config(
        self,
        step: str,
        *,
        epochs: int | None,
        imgsz: int | None,
        batch: int | None,
        patience: int | None,
    ) -> dict[str, Any]:
        config = self._training_defaults(step)
        if epochs is not None:
            config["epochs"] = int(epochs)
        if imgsz is not None:
            config["imgsz"] = int(imgsz)
        if batch is not None:
            config["batch"] = int(batch)
        if patience is not None:
            config["patience"] = int(patience)
        return config

    @classmethod
    def _resolve_ultralytics_device(cls, device_value: Any) -> str:
        return cls._resolve_ultralytics_device_details(device_value)[0]

    @classmethod
    def _resolve_ultralytics_device_details(cls, device_value: Any) -> tuple[str, str]:
        requested = str(device_value or "").strip()
        if requested and requested.lower() != "auto":
            return requested, "manual_override"

        try:
            import torch
        except Exception:
            return "cpu", "torch_import_failed"

        if bool(getattr(getattr(torch, "cuda", None), "is_available", lambda: False)()):
            if cls._torchvision_cuda_nms_available(torch_module=torch):
                return "0", "cuda_available"
            return "cpu", "cuda_visible_but_torchvision_nms_unavailable"

        mps_backend = getattr(getattr(torch, "backends", None), "mps", None)
        if bool(getattr(mps_backend, "is_available", lambda: False)()):
            return "mps", "mps_available"

        return "cpu", "cpu_only"

    @staticmethod
    def _torchvision_cuda_nms_available(*, torch_module: Any | None = None, torchvision_module: Any | None = None) -> bool:
        torch = torch_module
        torchvision = torchvision_module
        try:
            if torch is None:
                import torch as imported_torch
                torch = imported_torch
            if torchvision is None:
                import torchvision as imported_torchvision
                torchvision = imported_torchvision
        except Exception:
            return False

        if not bool(getattr(getattr(torch, "cuda", None), "is_available", lambda: False)()):
            return False

        try:
            boxes = torch.tensor(
                [[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 9.0, 9.0]],
                device="cuda:0",
            )
            scores = torch.tensor([0.9, 0.8], device="cuda:0")
            torchvision.ops.nms(boxes, scores, 0.5)
            return True
        except Exception:
            return False

    @staticmethod
    def _wall_polygon(
        wall: dict[str, Any],
        *,
        width: int,
        height: int,
        scale_factor: float,
    ) -> list[tuple[float, float]]:
        x1 = float(wall.get("x1", 0.0))
        y1 = float(wall.get("y1", 0.0))
        x2 = float(wall.get("x2", 0.0))
        y2 = float(wall.get("y2", 0.0))
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return [(x1, y1), (x1 + 1.0, y1), (x1 + 1.0, y1 + 1.0), (x1, y1 + 1.0)]
        half_thickness = max(
            0.5,
            float(wall.get("thickness", wall.get("thickness_px", 1.0)) or 1.0) / max(scale_factor or 1.0, 1e-6) / 2.0,
        )
        nx = -dy / length
        ny = dx / length
        points = [
            (x1 + nx * half_thickness, y1 + ny * half_thickness),
            (x2 + nx * half_thickness, y2 + ny * half_thickness),
            (x2 - nx * half_thickness, y2 - ny * half_thickness),
            (x1 - nx * half_thickness, y1 - ny * half_thickness),
        ]
        return [
            (min(max(px, 0.0), float(width)), min(max(py, 0.0), float(height)))
            for px, py in points
        ]

    @staticmethod
    def _polygon_to_label_line(
        class_id: int,
        points: list[tuple[float, float]],
        *,
        width: int,
        height: int,
    ) -> str:
        normalized: list[str] = []
        for x, y in points:
            normalized.append(f"{min(max(x / max(width, 1), 0.0), 1.0):.6f}")
            normalized.append(f"{min(max(y / max(height, 1), 0.0), 1.0):.6f}")
        return f"{class_id} " + " ".join(normalized)


def run_training_job_main(run_id: str) -> int:
    """Entrypoint helper used by the standalone training runner script."""

    from backend.bootstrap import ensure_runtime_directories
    from backend.database import SessionLocal, init_db
    from backend.modules.shared.infrastructure.storage import StorageService

    ensure_runtime_directories()
    init_db()
    session = SessionLocal()
    try:
        service = RecognitionTrainingManagementService(session, StorageService())
        service.run_training_job(run_id)
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        session.close()

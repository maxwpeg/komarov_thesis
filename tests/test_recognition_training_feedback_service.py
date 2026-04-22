"""Tests for step-level training feedback capture and export."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from fastapi import UploadFile

import backend.database as database
from backend.models import (
    Door,
    FloorPlan,
    FloorplanRecognition,
    PipelineDetectionSnapshot,
    Project,
    RecognitionFeedbackExample,
    Wall,
    Window,
)
from backend.modules.pipeline.application.state_manager import PipelineStateManager
from backend.services.pipeline_service import PipelineService
from backend.services.recognition_training_feedback_service import RecognitionTrainingFeedbackService
from backend.services.storage_service import StorageService


def _create_project_and_floor_plan(db, storage: StorageService, tmp_path: Path, *, filename: str, number: int) -> FloorPlan:
    upload_path = tmp_path / filename
    Image.new("RGB", (256, 256), color="white").save(upload_path)

    project = Project(
        name="Project",
        project_type="PS",
        number=number,
        year=2026,
        code=f"RP-ZK-{number}/26-PS",
        contractor="Contractor",
        engineer="Engineer",
        cpe="CPE",
        checker="Checker",
        facility="Facility",
        facility_address="Address",
        project_description="Description",
        stage="R",
        number_of_floors=1,
    )
    db.add(project)
    db.flush()

    with upload_path.open("rb") as image_file:
        saved = storage.save_upload(UploadFile(filename=filename, file=image_file), 1, 1)
    floor_plan = FloorPlan(
        project_id=project.id,
        floor_number=1,
        name="Floor 1",
        scale_factor=10.0,
        original_image_path=saved.relative_path,
        image_width=saved.width,
        image_height=saved.height,
    )
    db.add(floor_plan)
    db.commit()
    return floor_plan


def _validated_state(*steps: str) -> dict:
    manager = PipelineStateManager()
    state = manager.load(None, "non_addressable")
    for step in steps:
        state = manager.set_step_status(state, step, "validated", committed=True, bump_revision=True)
    return state


def test_submit_step_feedback_uses_pipeline_snapshot_not_legacy_recognition(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="step-feedback.png", number=11)
        wall = Wall(floor_plan_id=floor_plan.id, x1=0, y1=0, x2=100, y2=0, thickness=200, length_m=1.0, length_source="manual")
        recognition = FloorplanRecognition(
            floor_plan_id=floor_plan.id,
            recognition_result={"walls": [{"id": "legacy", "x2": 999}]},
            status="completed",
        )
        db.add_all([wall, recognition])
        db.flush()
        floor_plan.pipeline_state = _validated_state("walls")
        db.add(
            PipelineDetectionSnapshot(
                floor_plan_id=floor_plan.id,
                step="walls",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot={
                    "step": "walls",
                    "image": {
                        "width": floor_plan.image_width,
                        "height": floor_plan.image_height,
                        "original_image_path": floor_plan.original_image_path,
                    },
                    "walls": [{"id": wall.id, "x1": 0, "y1": 0, "x2": 80, "y2": 0, "thickness": 200}],
                    "dimensions": [],
                },
            )
        )
        db.commit()

        wall.x2 = 120
        db.commit()

        service = RecognitionTrainingFeedbackService(db, storage)
        result = service.submit_step_feedback(floor_plan.id, step="walls", step_revision=1)
        db.commit()

        example = db.query(RecognitionFeedbackExample).filter(RecognitionFeedbackExample.id == result["feedback_id"]).one()
        assert example.source_snapshot["walls"][0]["x2"] == 80
        assert example.corrected_snapshot["walls"][0]["x2"] == 120
        assert example.source_snapshot["walls"][0]["x2"] != recognition.recognition_result["walls"][0]["x2"]
    finally:
        db.close()


def test_submit_step_feedback_upserts_per_step_and_revision(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="step-feedback-upsert.png", number=12)
        wall = Wall(floor_plan_id=floor_plan.id, x1=0, y1=0, x2=100, y2=0, thickness=200, length_m=1.0, length_source="manual")
        door = Door(floor_plan_id=floor_plan.id, x=30, y=-5, width=20, height=10, wall_id=1, rotation_deg=0)
        window = Window(floor_plan_id=floor_plan.id, x=60, y=-5, width=20, height=10, wall_id=1, rotation_deg=0)
        db.add_all([wall, door, window])
        db.flush()
        door.wall_id = wall.id
        window.wall_id = wall.id
        floor_plan.pipeline_state = _validated_state("walls", "openings")
        recognition = FloorplanRecognition(floor_plan_id=floor_plan.id, recognition_result={"id": 1}, status="completed")
        db.add(recognition)
        db.add_all([
            PipelineDetectionSnapshot(
                floor_plan_id=floor_plan.id,
                step="walls",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot={
                    "step": "walls",
                    "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                    "walls": [{"id": wall.id, "x1": 0, "y1": 0, "x2": 90, "y2": 0, "thickness": 200}],
                    "dimensions": [],
                },
            ),
            PipelineDetectionSnapshot(
                floor_plan_id=floor_plan.id,
                step="openings",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot={
                    "step": "openings",
                    "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                    "walls": [{"id": wall.id, "x1": 0, "y1": 0, "x2": 100, "y2": 0, "thickness": 200}],
                    "openings": [{"id": 1, "type": "door", "wall_id": wall.id, "bbox": [25, -5, 45, 5]}],
                },
            ),
        ])
        db.commit()

        service = RecognitionTrainingFeedbackService(db, storage)
        first = service.submit_step_feedback(floor_plan.id, step="walls", step_revision=1, notes="first")
        second = service.submit_step_feedback(floor_plan.id, step="openings", step_revision=1)
        db.commit()

        updated = service.submit_step_feedback(floor_plan.id, step="walls", step_revision=1, notes="updated")
        db.commit()

        examples = (
            db.query(RecognitionFeedbackExample)
            .filter(RecognitionFeedbackExample.floor_plan_id == floor_plan.id)
            .order_by(RecognitionFeedbackExample.step.asc())
            .all()
        )
        assert len(examples) == 2
        assert {example.step for example in examples} == {"walls", "openings"}
        assert first["feedback_id"] == updated["feedback_id"]
        assert second["step"] == "openings"
        assert next(example for example in examples if example.step == "walls").notes == "updated"
    finally:
        db.close()


def test_submit_step_feedback_backfills_missing_legacy_snapshot(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="legacy-step-feedback.png", number=15)
        wall = Wall(
            floor_plan_id=floor_plan.id,
            x1=0,
            y1=0,
            x2=100,
            y2=0,
            thickness=200,
            length_m=1.0,
            length_source="manual",
        )
        db.add(wall)
        db.flush()
        floor_plan.pipeline_state = _validated_state("walls")
        db.commit()

        service = RecognitionTrainingFeedbackService(db, storage)
        result = service.submit_step_feedback(floor_plan.id, step="walls", step_revision=1)
        db.commit()

        snapshot = (
            db.query(PipelineDetectionSnapshot)
            .filter(
                PipelineDetectionSnapshot.floor_plan_id == floor_plan.id,
                PipelineDetectionSnapshot.step == "walls",
                PipelineDetectionSnapshot.step_revision == 1,
            )
            .one()
        )
        example = db.query(RecognitionFeedbackExample).filter(RecognitionFeedbackExample.id == result["feedback_id"]).one()

        assert snapshot.source_snapshot["source_kind"] == "legacy_backfill_current_state"
        assert example.source_snapshot["source_kind"] == "legacy_backfill_current_state"
        assert example.diff_summary["changed"] is False
        assert result["status"] == "approved"
    finally:
        db.close()


def test_export_feedback_batches_separates_steps_and_writes_derived_assets(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="export-batches.png", number=13)
        export_root = tmp_path / "exports"

        for revision in range(1, 11):
            db.add(
                RecognitionFeedbackExample(
                    floor_plan_id=floor_plan.id,
                    recognition_id=None,
                    step="walls",
                    step_revision=revision,
                    detector_version="cv.hybrid.v1",
                    source_snapshot={
                        "step": "walls",
                        "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                        "walls": [{"id": revision, "x1": 10, "y1": 10 + revision, "x2": 120, "y2": 10 + revision, "thickness": 18}],
                        "dimensions": [],
                    },
                    corrected_snapshot={
                        "step": "walls",
                        "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                        "walls": [{"id": revision, "x1": 10, "y1": 10 + revision, "x2": 150, "y2": 10 + revision, "thickness": 22}],
                        "dimensions": [],
                    },
                    diff_summary={"changed": True, "hardness_score": 4.0, "counts": {"missed": 1}},
                    hardness_score=4.0,
                    status="approved",
                )
            )

        for revision in range(1, 11):
            corrected_openings = []
            source_openings = []
            for index in range(20):
                opening_type = "door" if index % 2 == 0 else "window"
                corrected_openings.append(
                    {
                        "id": index + 1,
                        "type": opening_type,
                        "wall_id": 1,
                        "bbox": [20 + index * 4, 40, 34 + index * 4, 54],
                    }
                )
                if index < 18:
                    source_openings.append(
                        {
                            "id": index + 1,
                            "type": opening_type,
                            "wall_id": 1,
                            "bbox": [20 + index * 4, 40, 34 + index * 4, 54],
                        }
                    )
            db.add(
                RecognitionFeedbackExample(
                    floor_plan_id=floor_plan.id,
                    recognition_id=None,
                    step="openings",
                    step_revision=revision,
                    detector_version="cv.hybrid.v1",
                    source_snapshot={
                        "step": "openings",
                        "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                        "walls": [{"id": 1, "x1": 0, "y1": 40, "x2": 220, "y2": 40, "thickness": 20}],
                        "openings": source_openings,
                    },
                    corrected_snapshot={
                        "step": "openings",
                        "image": {"width": floor_plan.image_width, "height": floor_plan.image_height, "original_image_path": floor_plan.original_image_path},
                        "walls": [{"id": 1, "x1": 0, "y1": 40, "x2": 220, "y2": 40, "thickness": 20}],
                        "openings": corrected_openings,
                    },
                    diff_summary={"changed": True, "hardness_score": 4.5, "counts": {"missed": 2}},
                    hardness_score=4.5,
                    status="approved",
                )
            )
        db.commit()

        service = RecognitionTrainingFeedbackService(db, storage)
        result = service.export_feedback_batches(batch_id="batch-test", output_root=export_root)

        assert {batch["step"] for batch in result["batches"]} == {"walls", "openings"}

        walls_batch = next(batch for batch in result["batches"] if batch["step"] == "walls")
        openings_batch = next(batch for batch in result["batches"] if batch["step"] == "openings")
        walls_manifest = Path(walls_batch["summary"]["manifest_path"])
        openings_manifest = Path(openings_batch["summary"]["manifest_path"])
        assert walls_manifest.exists()
        assert openings_manifest.exists()

        walls_entries = [json.loads(line) for line in walls_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        openings_entries = [json.loads(line) for line in openings_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert Path(export_root / "batch-test_walls" / walls_entries[0]["derived"]["wall_mask_path"]).exists()
        first_crop = openings_entries[0]["derived"]["crops"][0]["image_path"]
        assert Path(export_root / "batch-test_openings" / first_crop).exists()

        exported_examples = db.query(RecognitionFeedbackExample).filter(RecognitionFeedbackExample.status == "exported").all()
        assert len(exported_examples) == 20
    finally:
        db.close()


def test_pipeline_state_exposes_current_step_feedback_submission(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="pipeline-state-feedback.png", number=14)
        wall = Wall(floor_plan_id=floor_plan.id, x1=0, y1=0, x2=100, y2=0, thickness=200, length_m=1.0, length_source="manual")
        db.add(wall)
        db.flush()
        floor_plan.pipeline_state = _validated_state("walls")
        db.add(
            RecognitionFeedbackExample(
                floor_plan_id=floor_plan.id,
                recognition_id=None,
                step="walls",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot={"step": "walls", "image": {"width": 256, "height": 256, "original_image_path": floor_plan.original_image_path}, "walls": [], "dimensions": []},
                corrected_snapshot={"step": "walls", "image": {"width": 256, "height": 256, "original_image_path": floor_plan.original_image_path}, "walls": [], "dimensions": []},
                diff_summary={"changed": False, "hardness_score": 0.0, "counts": {}},
                hardness_score=0.0,
                status="approved",
            )
        )
        db.commit()

        service = PipelineService(db, storage)
        state = service.get_pipeline_state(floor_plan.id)

        assert state.steps["walls"].feedback_status == "approved"
        assert state.steps["walls"].feedback_example_id is not None
        assert state.steps["walls"].feedback_submitted_revision == 1
    finally:
        db.close()

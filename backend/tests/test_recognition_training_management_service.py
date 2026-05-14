"""Tests for recognition training management and fake training runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from fastapi import UploadFile
from PIL import Image
import pytest

import backend.database as database
from backend.config import settings
from backend.models import FloorPlan, Project, RecognitionFeedbackExample, RecognitionTrainingBatch, RecognitionTrainingBatchExample, RecognitionTrainingRun
from backend.errors import AppError
from backend.services.recognition_training_management_service import RecognitionTrainingManagementService
from backend.services.storage_service import StorageService


def _create_floor_plan(db, storage: StorageService, tmp_path: Path, *, filename: str, number: int) -> FloorPlan:
    image_path = tmp_path / filename
    save_kwargs = {}
    if image_path.suffix.lower() in {".jpg", ".jpeg", ".jfif"}:
        save_kwargs["format"] = "JPEG"
    Image.new("RGB", (320, 240), color="white").save(image_path, **save_kwargs)

    project = Project(
        name=f"Project {number}",
        project_type="PS",
        number=number,
        year=2026,
        code=f"RP-ZK-{number}/26-PS",
        contractor="Contractor",
        engineer="Engineer",
        cpe="CPE",
        checker="Checker",
        facility=f"Facility {number}",
        facility_address="Address",
        project_description="Description",
        stage="R",
        number_of_floors=1,
    )
    db.add(project)
    db.flush()

    with image_path.open("rb") as image_file:
        saved = storage.save_upload(UploadFile(filename=filename, file=image_file), project.id, 1)
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
    db.refresh(floor_plan)
    return floor_plan


def _wall_snapshot(floor_plan: FloorPlan, *, x2: float) -> dict:
    return {
        "step": "walls",
        "image": {
            "width": floor_plan.image_width,
            "height": floor_plan.image_height,
            "original_image_path": floor_plan.original_image_path,
            "scale_factor": floor_plan.scale_factor,
        },
        "walls": [{"id": 1, "x1": 20, "y1": 40, "x2": x2, "y2": 40, "thickness": 200}],
        "dimensions": [],
    }


def test_init_db_backfills_legacy_training_batch_links(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_floor_plan(db, storage, tmp_path, filename="legacy-link.png", number=31)
        batch = RecognitionTrainingBatch(
            batch_id="legacy-batch",
            step="walls",
            detector_version="cv.hybrid.v1",
            status="exported",
            export_dir=str((tmp_path / "legacy-batch").resolve()),
            summary={},
        )
        db.add(batch)
        db.flush()
        example = RecognitionFeedbackExample(
            floor_plan_id=floor_plan.id,
            recognition_id=None,
            training_batch_id=batch.id,
            step="walls",
            step_revision=1,
            detector_version="cv.hybrid.v1",
            source_snapshot=_wall_snapshot(floor_plan, x2=120),
            corrected_snapshot=_wall_snapshot(floor_plan, x2=160),
            diff_summary={"changed": True, "hardness_score": 4.0, "counts": {"missed": 1}},
            hardness_score=4.0,
            status="exported",
            curation_status="approved",
        )
        db.add(example)
        db.commit()

        database.init_db()

        links = db.query(RecognitionTrainingBatchExample).filter(RecognitionTrainingBatchExample.feedback_example_id == example.id).all()
        assert len(links) == 1
        assert links[0].training_batch_id == batch.id
    finally:
        db.close()


def test_fake_training_run_builds_dataset_and_marks_run_succeeded(isolated_database, tmp_path: Path, monkeypatch):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_floor_plan(db, storage, tmp_path, filename="training-run.png", number=32)
        for revision in range(1, 51):
            db.add(
                RecognitionFeedbackExample(
                    floor_plan_id=floor_plan.id,
                    recognition_id=None,
                    step="walls",
                    step_revision=revision,
                    detector_version="cv.hybrid.v1",
                    source_snapshot=_wall_snapshot(floor_plan, x2=120 + revision),
                    corrected_snapshot=_wall_snapshot(floor_plan, x2=150 + revision),
                    diff_summary={"changed": True, "hardness_score": 4.0, "counts": {"missed": 1}},
                    hardness_score=4.0,
                    status="approved",
                    curation_status="approved",
                )
            )
        db.commit()

        service = RecognitionTrainingManagementService(db, storage)
        created = service.create_run(step="walls", spawn_process=False)
        monkeypatch.setenv("RECOGNITION_TRAINING_FAKE_RUN", "1")
        completed = service.run_training_job(created["run_id"])

        assert completed["status"] == "succeeded"
        artifact_dir = storage.absolute_path(completed["artifact_dir"])
        assert artifact_dir is not None
        assert (artifact_dir / "best.pt").exists()
        assert (artifact_dir / "last.pt").exists()
        assert (artifact_dir / "dataset" / "dataset.yaml").exists()
        assert completed["batch"]["summary"]["sample_count"] == 50
        assert any((artifact_dir / "dataset" / "images" / "train").iterdir())
        assert any((artifact_dir / "dataset" / "images" / "val").iterdir())
        assert completed["metrics_summary"]["sample_count"] == 50

        used_examples = db.query(RecognitionFeedbackExample).filter(RecognitionFeedbackExample.status == "used").all()
        assert len(used_examples) == 50
    finally:
        monkeypatch.delenv("RECOGNITION_TRAINING_FAKE_RUN", raising=False)
        db.close()


def test_create_run_can_be_forced_below_recommended_batch_size(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_floor_plan(db, storage, tmp_path, filename="forced-run.png", number=33)
        db.add(
            RecognitionFeedbackExample(
                floor_plan_id=floor_plan.id,
                recognition_id=None,
                step="walls",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot=_wall_snapshot(floor_plan, x2=120),
                corrected_snapshot=_wall_snapshot(floor_plan, x2=160),
                diff_summary={"changed": True, "hardness_score": 4.0, "counts": {"missed": 1}},
                hardness_score=4.0,
                status="approved",
                curation_status="approved",
            )
        )
        db.commit()

        service = RecognitionTrainingManagementService(db, storage)
        with pytest.raises(AppError) as exc_info:
            service.create_run(step="walls", force=False, spawn_process=False)
        assert exc_info.value.code == "recognition_training_batch_not_ready"

        created = service.create_run(step="walls", force=True, spawn_process=False)

        assert created["status"] == "queued"
        assert created["config"]["force"] is True
        assert created["batch"]["summary"]["sample_count"] == 1
        assert created["batch"]["summary"]["forced"] is True
    finally:
        db.close()


def test_forced_single_sample_run_duplicates_into_val_split(isolated_database, tmp_path: Path, monkeypatch):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_floor_plan(db, storage, tmp_path, filename="single-sample-run.jfif", number=36)
        db.add(
            RecognitionFeedbackExample(
                floor_plan_id=floor_plan.id,
                recognition_id=None,
                step="walls",
                step_revision=1,
                detector_version="cv.hybrid.v1",
                source_snapshot=_wall_snapshot(floor_plan, x2=120),
                corrected_snapshot=_wall_snapshot(floor_plan, x2=160),
                diff_summary={"changed": True, "hardness_score": 4.0, "counts": {"missed": 1}},
                hardness_score=4.0,
                status="approved",
                curation_status="approved",
            )
        )
        db.commit()

        service = RecognitionTrainingManagementService(db, storage)
        created = service.create_run(step="walls", force=True, spawn_process=False)
        monkeypatch.setenv("RECOGNITION_TRAINING_FAKE_RUN", "1")
        completed = service.run_training_job(created["run_id"])

        artifact_dir = storage.absolute_path(completed["artifact_dir"])
        assert artifact_dir is not None
        train_images = list((artifact_dir / "dataset" / "images" / "train").iterdir())
        val_images = list((artifact_dir / "dataset" / "images" / "val").iterdir())

        assert completed["metrics_summary"]["sample_count"] == 1
        assert completed["metrics_summary"]["dataset_item_count"] == 2
        assert len(train_images) == 1
        assert len(val_images) == 1
        assert train_images[0].name == val_images[0].name
        assert train_images[0].suffix.lower() == ".png"
    finally:
        monkeypatch.delenv("RECOGNITION_TRAINING_FAKE_RUN", raising=False)
        db.close()


def test_get_overview_handles_legacy_naive_batch_timestamps(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        _create_floor_plan(db, storage, tmp_path, filename="naive-batch.png", number=34)
        db.add(
            RecognitionTrainingBatch(
                batch_id="legacy-naive-batch",
                step="walls",
                detector_version="cv.hybrid.v1",
                status="exported",
                export_dir=str((tmp_path / "legacy-naive-batch").resolve()),
                summary={},
                created_at=datetime.now() - timedelta(days=21),
                exported_at=datetime.now() - timedelta(days=20),
            )
        )
        db.commit()

        service = RecognitionTrainingManagementService(db, storage)
        overview = service.get_overview()

        walls_overview = next(item for item in overview["steps"] if item["step"] == "walls")
        assert walls_overview["next_batch_hint"]["reason"] == "no_approved_examples"
        assert walls_overview["last_batch"]["batch_id"] == "legacy-naive-batch"
    finally:
        db.close()


def test_spawn_training_process_adds_project_root_to_pythonpath(isolated_database, tmp_path: Path, monkeypatch):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        service = RecognitionTrainingManagementService(db, storage)
        log_path = tmp_path / "training.log"
        captured: dict[str, object] = {}

        class DummyProcess:
            def __init__(self) -> None:
                self.pid = 12345

        def fake_popen(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return DummyProcess()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)

        service._spawn_training_process("run-123", log_path)

        kwargs = captured["kwargs"]
        env = kwargs["env"]
        assert str(settings.project_root.resolve()) in env["PYTHONPATH"].split(os.pathsep)
        assert kwargs["cwd"] == str(settings.project_root)
    finally:
        db.close()


def test_list_runs_marks_stale_queued_run_as_failed(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_floor_plan(db, storage, tmp_path, filename="stale-queued.png", number=35)
        batch = RecognitionTrainingBatch(
            batch_id="stale-queued-batch",
            step="walls",
            detector_version="cv.hybrid.v1",
            status="exported",
            export_dir=str((tmp_path / "stale-queued-batch").resolve()),
            summary={},
        )
        db.add(batch)
        db.flush()

        log_path = tmp_path / "stdout.log"
        log_path.write_text(
            "Traceback (most recent call last):\nModuleNotFoundError: No module named 'backend'\n",
            encoding="utf-8",
        )
        run = RecognitionTrainingRun(
            run_id="stale-queued-run",
            training_batch_id=batch.id,
            step="walls",
            status="queued",
            config={},
            artifact_dir=str(tmp_path),
            log_path=str(log_path),
            requested_at=(datetime.now(timezone.utc) - timedelta(minutes=2)).replace(tzinfo=None),
        )
        db.add(run)
        db.commit()

        service = RecognitionTrainingManagementService(db, storage)
        runs = service.list_runs()

        assert runs[0]["status"] == "failed"
        refreshed = db.query(RecognitionTrainingRun).filter_by(run_id="stale-queued-run").one()
        assert refreshed.status == "failed"
        assert "ModuleNotFoundError" in (refreshed.error_message or "")
    finally:
        db.close()


def test_resolve_ultralytics_device_uses_cpu_when_auto_and_cuda_unavailable():
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
    )
    original = sys.modules.get("torch")
    original_torchvision = sys.modules.get("torchvision")
    sys.modules["torch"] = fake_torch
    try:
        assert RecognitionTrainingManagementService._resolve_ultralytics_device("auto") == "cpu"
    finally:
        if original is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = original
        if original_torchvision is None:
            sys.modules.pop("torchvision", None)
        else:
            sys.modules["torchvision"] = original_torchvision


def test_resolve_ultralytics_batch_size_forces_cpu_segment_training_to_one():
    assert RecognitionTrainingManagementService._resolve_ultralytics_batch_size(-1, "cpu", task="segment") == 1
    assert RecognitionTrainingManagementService._resolve_ultralytics_batch_size(16, "cpu", task="segment") == 1


def test_resolve_ultralytics_batch_size_preserves_cuda_auto_batch():
    assert RecognitionTrainingManagementService._resolve_ultralytics_batch_size(-1, "0", task="segment") == -1
    assert RecognitionTrainingManagementService._resolve_ultralytics_batch_size(8, "0", task="segment") == 8


def test_resolve_ultralytics_device_uses_first_cuda_device_when_available():
    def fake_tensor(data, *args, **kwargs):
        return {"data": data, "device": kwargs.get("device")}

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        tensor=fake_tensor,
    )
    fake_torchvision = SimpleNamespace(
        ops=SimpleNamespace(nms=lambda boxes, scores, iou_threshold: [0])
    )
    original = sys.modules.get("torch")
    original_torchvision = sys.modules.get("torchvision")
    sys.modules["torch"] = fake_torch
    sys.modules["torchvision"] = fake_torchvision
    try:
        assert RecognitionTrainingManagementService._resolve_ultralytics_device("auto") == "0"
    finally:
        if original is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = original
        if original_torchvision is None:
            sys.modules.pop("torchvision", None)
        else:
            sys.modules["torchvision"] = original_torchvision


def test_resolve_ultralytics_device_falls_back_to_cpu_when_cuda_nms_is_unavailable():
    def fake_tensor(data, *args, **kwargs):
        return {"data": data, "device": kwargs.get("device")}

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        tensor=fake_tensor,
    )
    fake_torchvision = SimpleNamespace(
        ops=SimpleNamespace(nms=lambda boxes, scores, iou_threshold: (_ for _ in ()).throw(NotImplementedError("nms unavailable")))
    )
    original = sys.modules.get("torch")
    original_torchvision = sys.modules.get("torchvision")
    sys.modules["torch"] = fake_torch
    sys.modules["torchvision"] = fake_torchvision
    try:
        resolved, reason = RecognitionTrainingManagementService._resolve_ultralytics_device_details("auto")
        assert resolved == "cpu"
        assert reason == "cuda_visible_but_torchvision_nms_unavailable"
    finally:
        if original is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = original
        if original_torchvision is None:
            sys.modules.pop("torchvision", None)
        else:
            sys.modules["torchvision"] = original_torchvision

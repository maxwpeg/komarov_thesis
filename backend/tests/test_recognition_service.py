"""Recognition service tests."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from fastapi import UploadFile
import pytest

import backend.database as database
from backend.errors import AppError
from backend.models import (
    Dimension,
    FloorPlan,
    FloorplanRecognition,
    Project,
    RecognitionFeedbackSample,
    Room as RoomModel,
    Wall as WallModel,
)
from backend.services.recognition_service import RecognitionService
from backend.services.storage_service import StorageService
from floorplan.floorplan_types import Dimension as DetectedDimension
from floorplan.floorplan_types import LineSegment, ProcessingResult, Room, Wall


def _create_project_and_floor_plan(db, storage: StorageService, tmp_path: Path, *, filename: str, number: int) -> FloorPlan:
    upload_path = tmp_path / filename
    Image.new("RGB", (240, 240), color="white").save(upload_path)

    project = Project(
        name="Project",
        project_type="PS",
        number=number,
        year=2026,
        code=f"Р Рџ-Р—Рљ-{number}/26-PS",
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


def test_recognition_failure_persists_failed_state(isolated_database, monkeypatch, tmp_path: Path):
    upload_path = tmp_path / "floor.png"
    Image.new("RGB", (240, 240), color="white").save(upload_path)

    db = database.SessionLocal()
    try:
        project = Project(
            name="Project",
            project_type="PS",
            number=1,
            year=2026,
            code="РП-ЗК-1/26-PS",
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

        storage = StorageService()
        with upload_path.open("rb") as image_file:
            saved = storage.save_upload(UploadFile(filename="floor.png", file=image_file), 1, 1)
        floor_plan = FloorPlan(
            project_id=project.id,
            floor_number=1,
            name="Floor 1",
            scale_factor=1.0,
            original_image_path=saved.relative_path,
            image_width=saved.width,
            image_height=saved.height,
        )
        db.add(floor_plan)
        db.commit()

        def fail(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "backend.floorplan_integration.FloorplanRecognitionIntegrator.recognize_floor_plan",
            fail,
        )

        service = RecognitionService(db, storage)
        try:
            service.process_floor_plan(floor_plan.id, debug=False)
        except Exception:
            pass

        recognition = service.get_recognition(floor_plan.id)
        assert recognition.status == "failed"
        assert recognition.recognition_result == {"error": "boom"}
    finally:
        db.close()


def test_recognition_persists_rooms_dimensions_and_preserves_room_name(
    isolated_database,
    monkeypatch,
    tmp_path: Path,
):
    upload_path = tmp_path / "floor-success.png"
    Image.new("RGB", (240, 240), color="white").save(upload_path)

    db = database.SessionLocal()
    try:
        project = Project(
            name="Project",
            project_type="PS",
            number=2,
            year=2026,
            code="РП-ЗК-2/26-PS",
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

        storage = StorageService()
        with upload_path.open("rb") as image_file:
            saved = storage.save_upload(UploadFile(filename="floor-success.png", file=image_file), 1, 1)
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

        # Existing user-named room should be preserved on re-recognition.
        existing_room = RoomModel(
            floor_plan_id=floor_plan.id,
            name="Кухня",
            room_type="kitchen",
            room_number="10",
            boundary_points=[[10, 10], [50, 10], [50, 50], [10, 50]],
        )
        existing_room.calculate_area(scale_factor=floor_plan.scale_factor)
        existing_room.calculate_perimeter(scale_factor=floor_plan.scale_factor)
        existing_room.calculate_center()
        db.add(existing_room)
        db.commit()

        fake_result = ProcessingResult(
            image_width=64,
            image_height=64,
            walls=[
                Wall(
                    id=1,
                    midline=LineSegment(5, 20, 55, 20, length=50, angle=0),
                    thickness_px=20,
                    angle_deg=0.0,
                    confidence=0.9,
                )
            ],
            openings=[],
            rooms=[
                Room(
                    id=1,
                    room_number="1",
                    name="Помещение 1",
                    boundary_points=[[10, 10], [50, 10], [50, 50], [10, 50]],
                    center=(30, 30),
                    area_px=1600,
                )
            ],
            dimensions=[
                DetectedDimension(
                    id=1,
                    x=28,
                    y=18,
                    value=2.4,
                    unit="m",
                    text="2400",
                    wall_id=1,
                    room_id=1,
                )
            ],
        )

        def fake_recognize(self, *_args, **_kwargs):
            return fake_result, {"success": True}

        monkeypatch.setattr(
            "backend.floorplan_integration.FloorplanRecognitionIntegrator.recognize_floor_plan",
            fake_recognize,
        )

        service = RecognitionService(db, storage)
        recognition_id, walls_count, doors_count, windows_count, rooms_count, dimensions_count = service.process_floor_plan(
            floor_plan.id,
            debug=False,
        )

        assert recognition_id is not None
        assert walls_count == 1
        assert doors_count == 0
        assert windows_count == 0
        assert rooms_count == 1
        assert dimensions_count == 1

        persisted_room = db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan.id).one()
        assert persisted_room.name == "Кухня"

        persisted_wall = db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan.id).one()
        persisted_dimension = db.query(Dimension).filter(Dimension.floor_plan_id == floor_plan.id).one()
        assert persisted_dimension.unit == "m"
        assert persisted_dimension.value == 2.4
        assert persisted_dimension.wall_id == persisted_wall.id
        assert persisted_dimension.room_id == persisted_room.id
    finally:
        db.close()


def test_submit_feedback_requires_existing_recognition(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="feedback-missing.png", number=3)
        service = RecognitionService(db, storage)

        with pytest.raises(AppError) as exc_info:
            service.submit_feedback_sample(floor_plan.id)

        assert exc_info.value.code == "recognition_not_found"
    finally:
        db.close()


def test_submit_feedback_upserts_corrected_architecture_snapshot(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="feedback-upsert.png", number=4)
        wall = WallModel(floor_plan_id=floor_plan.id, x1=0, y1=0, x2=40, y2=0, thickness=200)
        room = RoomModel(
            floor_plan_id=floor_plan.id,
            name="Исходное имя",
            room_type="office",
            room_number="1",
            boundary_points=[[0, 0], [40, 0], [40, 40], [0, 40]],
            center_x=20,
            center_y=20,
        )
        dimension = Dimension(
            floor_plan_id=floor_plan.id,
            x=20,
            y=5,
            value=4.0,
            unit="m",
            text="4.0",
        )
        recognition = FloorplanRecognition(
            floor_plan_id=floor_plan.id,
            recognition_result={"walls": [{"id": 1}], "rooms": [{"id": 1}]},
            status="completed",
        )
        db.add_all([wall, room, dimension, recognition])
        db.commit()

        room.name = "Исправленное имя"
        db.commit()

        service = RecognitionService(db, storage)
        sample_read = service.submit_feedback_sample(floor_plan.id)

        sample = db.query(RecognitionFeedbackSample).filter(RecognitionFeedbackSample.id == sample_read.id).one()
        assert sample.recognition_id == recognition.id
        assert sample.status == "approved"
        assert sample.corrected_snapshot["rooms"][0]["name"] == "Исправленное имя"
        assert set(sample.corrected_snapshot.keys()) == {"walls", "doors", "windows", "rooms", "dimensions"}

        sample.status = "exported"
        sample.export_batch_id = "old-batch"
        db.commit()
        room.name = "Исправленное имя 2"
        db.commit()

        second_read = service.submit_feedback_sample(floor_plan.id)
        assert second_read.id == sample_read.id

        samples = db.query(RecognitionFeedbackSample).filter(RecognitionFeedbackSample.recognition_id == recognition.id).all()
        assert len(samples) == 1
        assert samples[0].corrected_snapshot["rooms"][0]["name"] == "Исправленное имя 2"
        assert samples[0].status == "approved"
        assert samples[0].export_batch_id is None
        assert samples[0].exported_at is None
    finally:
        db.close()


def test_export_feedback_samples_writes_batch_and_marks_exported(isolated_database, tmp_path: Path):
    db = database.SessionLocal()
    try:
        storage = StorageService()
        floor_plan = _create_project_and_floor_plan(db, storage, tmp_path, filename="feedback-export.png", number=5)
        room = RoomModel(
            floor_plan_id=floor_plan.id,
            name="Комната",
            room_type="office",
            room_number="1",
            boundary_points=[[0, 0], [40, 0], [40, 40], [0, 40]],
            center_x=20,
            center_y=20,
        )
        recognition = FloorplanRecognition(
            floor_plan_id=floor_plan.id,
            recognition_result={"rooms": [{"id": 1, "name": "room"}]},
            status="completed",
        )
        db.add_all([room, recognition])
        db.commit()

        service = RecognitionService(db, storage)
        service.submit_feedback_sample(floor_plan.id)
        export_root = tmp_path / "exports"

        result = service.export_feedback_samples(batch_id="batch-test", output_root=export_root)

        batch_dir = export_root / "batch-test"
        manifest_path = batch_dir / "manifest.jsonl"
        assert result["batch_id"] == "batch-test"
        assert result["count"] == 1
        assert manifest_path.exists()

        manifest_entry = json.loads(manifest_path.read_text(encoding="utf-8").strip())
        assert manifest_entry["floor_plan_id"] == floor_plan.id
        assert manifest_entry["recognition_id"] == recognition.id
        assert (batch_dir / manifest_entry["image_path"]).exists()
        annotation_path = batch_dir / manifest_entry["annotation_path"]
        assert annotation_path.exists()
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        assert annotation["rooms"][0]["name"] == "Комната"

        sample = db.query(RecognitionFeedbackSample).one()
        assert sample.status == "exported"
        assert sample.export_batch_id == "batch-test"
        assert sample.exported_at is not None
    finally:
        db.close()

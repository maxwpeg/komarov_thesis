"""Recognition service tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from fastapi import UploadFile

import backend.database as database
from backend.models import Dimension, FloorPlan, Project, Room as RoomModel, Wall as WallModel
from backend.services.recognition_service import RecognitionService
from backend.services.storage_service import StorageService
from floorplan.floorplan_types import Dimension as DetectedDimension
from floorplan.floorplan_types import LineSegment, ProcessingResult, Room, Wall


def test_recognition_failure_persists_failed_state(isolated_database, monkeypatch, tmp_path: Path):
    upload_path = tmp_path / "floor.png"
    Image.new("RGB", (32, 32), color="white").save(upload_path)

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
    Image.new("RGB", (64, 64), color="white").save(upload_path)

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

"""SQLAlchemy repository for recognition workflows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import (
    Dimension as DimensionModel,
    Door as DoorModel,
    FloorPlan as FloorPlanModel,
    RecognitionFeedbackSample as RecognitionFeedbackSampleModel,
    FloorplanRecognition as FloorplanRecognitionModel,
    Room as RoomModel,
    Wall as WallModel,
    Window as WindowModel,
)


class SqlAlchemyRecognitionRepository:
    """SQLAlchemy-backed repository for recognition use cases."""

    def __init__(self, session: Session):
        self.session = session

    def get_floor_plan(self, floor_plan_id: int) -> FloorPlanModel:
        floor_plan = self.session.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    def get_recognition(self, floor_plan_id: int) -> FloorplanRecognitionModel | None:
        return (
            self.session.query(FloorplanRecognitionModel)
            .filter(FloorplanRecognitionModel.floor_plan_id == floor_plan_id)
            .first()
        )

    def create_recognition(self, data: dict) -> FloorplanRecognitionModel:
        return FloorplanRecognitionModel(**data)

    def get_feedback_sample(self, recognition_id: int) -> RecognitionFeedbackSampleModel | None:
        return (
            self.session.query(RecognitionFeedbackSampleModel)
            .filter(RecognitionFeedbackSampleModel.recognition_id == recognition_id)
            .first()
        )

    def list_feedback_samples_for_export(self) -> list[RecognitionFeedbackSampleModel]:
        return (
            self.session.query(RecognitionFeedbackSampleModel)
            .filter(
                RecognitionFeedbackSampleModel.status == "approved",
                RecognitionFeedbackSampleModel.exported_at.is_(None),
            )
            .order_by(RecognitionFeedbackSampleModel.submitted_at.asc(), RecognitionFeedbackSampleModel.id.asc())
            .all()
        )

    def create_feedback_sample(self, data: dict) -> RecognitionFeedbackSampleModel:
        return RecognitionFeedbackSampleModel(**data)

    def list_existing_rooms(self, floor_plan_id: int) -> list[RoomModel]:
        return self.session.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()

    def replace_detection_result(
        self,
        floor_plan_id: int,
        *,
        walls,
        doors,
        windows,
        rooms,
        dimensions,
    ) -> None:
        self.session.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).delete()
        self.session.query(DoorModel).filter(DoorModel.floor_plan_id == floor_plan_id).delete()
        self.session.query(WindowModel).filter(WindowModel.floor_plan_id == floor_plan_id).delete()
        self.session.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).delete()
        self.session.query(DimensionModel).filter(DimensionModel.floor_plan_id == floor_plan_id).delete()
        for wall in walls:
            self.session.add(wall)
        self.session.flush()
        for door in doors:
            self.session.add(door)
        for window in windows:
            self.session.add(window)
        for room in rooms:
            self.session.add(room)
        self.session.flush()
        for dimension in dimensions:
            self.session.add(dimension)
        self.session.flush()

    def add(self, entity) -> None:
        self.session.add(entity)

    def flush(self) -> None:
        self.session.flush()

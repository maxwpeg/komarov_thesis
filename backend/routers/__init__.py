"""FastAPI routers."""

from backend.routers.equipment import router as equipment_router
from backend.routers.elements import router as elements_router
from backend.routers.floor_plans import router as floor_plans_router
from backend.routers.pdf import router as pdf_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.projects import router as projects_router
from backend.routers.recognition import router as recognition_router
from backend.routers.recognition_training import router as recognition_training_router

__all__ = [
    "equipment_router",
    "elements_router",
    "floor_plans_router",
    "pdf_router",
    "pipeline_router",
    "projects_router",
    "recognition_router",
    "recognition_training_router",
]

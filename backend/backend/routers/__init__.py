"""FastAPI routers."""

from backend.routers.assets import router as assets_router
from backend.routers.audit import router as audit_router
from backend.routers.auth import router as auth_router
from backend.routers.background_tasks import router as background_tasks_router
from backend.routers.equipment import router as equipment_router
from backend.routers.elements import router as elements_router
from backend.routers.floor_plans import router as floor_plans_router
from backend.routers.pdf import router as pdf_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.projects import router as projects_router
from backend.routers.recognition import router as recognition_router
from backend.routers.recognition_training import router as recognition_training_router
from backend.routers.users import router as users_router

__all__ = [
    "assets_router",
    "audit_router",
    "auth_router",
    "background_tasks_router",
    "equipment_router",
    "elements_router",
    "floor_plans_router",
    "pdf_router",
    "pipeline_router",
    "projects_router",
    "recognition_router",
    "recognition_training_router",
    "users_router",
]

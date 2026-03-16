"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.bootstrap import configure_logging, ensure_runtime_directories, register_pdf_fonts
from backend.config import settings
from backend.database import engine, init_db
from backend.errors import install_exception_handlers
from backend.modules.shared.health.service import HealthService
from backend.modules.shared.observability.middleware import RequestContextMiddleware
from backend.routers import (
    elements_router,
    floor_plans_router,
    pdf_router,
    pipeline_router,
    projects_router,
    recognition_router,
)
from backend.schemas import HealthRead


logger = configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_runtime_directories()
    try:
        register_pdf_fonts()
    except FileNotFoundError:
        logger.warning("PDF fonts are unavailable; PDF generation may fail", exc_info=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Floor Plan API", version="1.0.0", lifespan=lifespan)
    health_service = HealthService(engine=engine, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware, logger=logger)

    app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")
    app.mount("/outputs", StaticFiles(directory=str(settings.outputs_dir)), name="outputs")
    app.mount("/debug_output", StaticFiles(directory=str(settings.debug_output_dir)), name="debug_output")

    install_exception_handlers(app)
    app.include_router(projects_router)
    app.include_router(floor_plans_router)
    app.include_router(elements_router)
    app.include_router(pipeline_router)
    app.include_router(recognition_router)
    app.include_router(pdf_router)

    @app.get("/", response_model=HealthRead, tags=["system"])
    def root() -> HealthRead:
        return health_service.live()

    @app.get("/health/live", response_model=HealthRead, tags=["system"])
    def health_live() -> HealthRead:
        return health_service.live()

    @app.get("/health/ready", tags=["system"])
    def health_ready() -> dict[str, object]:
        return health_service.ready()

    return app


app = create_app()

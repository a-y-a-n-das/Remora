from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)
from app.core.database import init_database, close_database
from app.api import health, memories

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_database()
    logger.info("application_starting")

    yield

    await close_database()
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="REMORA API",
        description="AI-powered visual memory engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.ALLOWED_ORIGINS != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    app.include_router(health.router)
    app.include_router(memories.router)

    return app


app = create_app()
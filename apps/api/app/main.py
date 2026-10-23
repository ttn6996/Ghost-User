"""Ghost-User API application entrypoint."""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.db.session import engine, Base, get_db
from app.api.v1 import api_v1_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Ghost-User API...")
    # Ensure artifacts directory exists
    artifact_path = Path(settings.ARTIFACT_STORAGE_DIR)
    artifact_path.mkdir(parents=True, exist_ok=True)
    # Ensure database tables exist (for dev/sqlite fallback before migrations)
    Base.metadata.create_all(bind=engine)
    logger.info("Ghost-User API initialized successfully.")
    yield
    logger.info("Shutting down Ghost-User API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS configuration
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.include_router(api_v1_router)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """General service health status."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "ghost-user-api",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def api_v1_health_check(db: Session = Depends(get_db)):
    """Versioned API health check."""
    return health_check(db=db)

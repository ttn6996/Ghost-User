"""Version 1 API router aggregation."""

from fastapi import APIRouter
from app.api.v1.projects import router as projects_router
from app.api.v1.test_cases import router as test_cases_router
from app.api.v1.test_runs import router as test_runs_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.artifacts import router as artifacts_router
from app.api.v1.stats import router as stats_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(projects_router)
api_v1_router.include_router(test_cases_router)
api_v1_router.include_router(test_runs_router)
api_v1_router.include_router(schedules_router)
api_v1_router.include_router(artifacts_router)
api_v1_router.include_router(stats_router)

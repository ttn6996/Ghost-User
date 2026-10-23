"""Real-time statistical aggregation endpoints calculated from verified DB records."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.db.session import get_db
from app.db.models import Project, TestCase, TestRun
from packages.shared.constants import RunStatus

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/overview")
def get_overview_statistics(db: Session = Depends(get_db)):
    """Computes real system-wide metrics and run distributions."""
    total_projects = db.scalar(select(func.count(Project.id))) or 0
    total_test_cases = db.scalar(select(func.count(TestCase.id))) or 0
    total_runs = db.scalar(select(func.count(TestRun.id))) or 0

    passed_runs = db.scalar(select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.PASSED.value)) or 0
    failed_runs = db.scalar(select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.FAILED.value)) or 0
    error_runs = db.scalar(select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.ERROR.value)) or 0
    running_runs = db.scalar(select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.RUNNING.value)) or 0
    queued_runs = db.scalar(select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.QUEUED.value)) or 0

    completed_runs = passed_runs + failed_runs + error_runs
    pass_rate = round((passed_runs / completed_runs * 100), 1) if completed_runs > 0 else 0.0

    # Fetch 5 most recent runs
    recent_runs_query = select(TestRun).order_by(desc(TestRun.created_at)).limit(5)
    recent_runs = db.execute(recent_runs_query).scalars().all()

    # Fetch 5 most recent failures
    recent_failures_query = (
        select(TestRun)
        .filter(TestRun.status.in_([RunStatus.FAILED.value, RunStatus.ERROR.value]))
        .order_by(desc(TestRun.created_at))
        .limit(5)
    )
    recent_failures = db.execute(recent_failures_query).scalars().all()

    return {
        "total_projects": total_projects,
        "total_test_cases": total_test_cases,
        "total_runs": total_runs,
        "passed_runs": passed_runs,
        "failed_runs": failed_runs,
        "error_runs": error_runs,
        "running_runs": running_runs,
        "queued_runs": queued_runs,
        "pass_rate_percentage": pass_rate,
        "recent_runs": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "trigger_type": r.trigger_type,
                "created_at": r.created_at,
            }
            for r in recent_runs
        ],
        "recent_failures": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "status": r.status,
                "error_summary": r.error_summary,
                "created_at": r.created_at,
            }
            for r in recent_failures
        ],
    }

"""Test Run endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, desc

from app.db.session import get_db
from app.db.models import TestRun, TestCase, Project
from app.schemas.test_run import (
    TestRunCreate,
    TestRunResponse,
    TestRunListResponse,
)
from packages.shared.constants import RunStatus

router = APIRouter(prefix="/test-runs", tags=["Test Runs"])


@router.post("", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
def trigger_test_run(payload: TestRunCreate, db: Session = Depends(get_db)):
    """Enqueues a new test run for background execution by the worker."""
    test_case = db.get(TestCase, payload.test_case_id)
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{payload.test_case_id}' not found",
        )

    test_run = TestRun(
        test_case_id=payload.test_case_id,
        status=RunStatus.QUEUED.value,
        trigger_type=payload.trigger_type.value,
    )
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    return test_run


@router.get("", response_model=TestRunListResponse)
def list_test_runs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    test_case_id: Optional[str] = Query(None, description="Filter by test case ID"),
    status: Optional[str] = Query(None, description="Filter by status (queued, running, passed, failed, error, cancelled)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Lists test runs with pagination and filters."""
    query = select(TestRun).options(joinedload(TestRun.step_results))

    if test_case_id:
        query = query.filter(TestRun.test_case_id == test_case_id)
    elif project_id:
        query = query.join(TestCase, TestRun.test_case_id == TestCase.id).filter(TestCase.project_id == project_id)

    if status:
        query = query.filter(TestRun.status == status)

    # Count total
    count_query = select(func.count(TestRun.id))
    if test_case_id:
        count_query = count_query.filter(TestRun.test_case_id == test_case_id)
    elif project_id:
        count_query = count_query.join(TestCase, TestRun.test_case_id == TestCase.id).filter(TestCase.project_id == project_id)
    if status:
        count_query = count_query.filter(TestRun.status == status)

    total = db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(desc(TestRun.created_at)).offset(offset).limit(page_size)
    runs = db.execute(query).unique().scalars().all()

    return TestRunListResponse(
        items=list(runs),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=TestRunResponse)
def get_test_run(run_id: str, db: Session = Depends(get_db)):
    """Retrieves detailed test run status, step timeline, logs, and artifacts."""
    query = (
        select(TestRun)
        .options(joinedload(TestRun.step_results))
        .filter(TestRun.id == run_id)
    )
    test_run = db.execute(query).unique().scalar_one_or_none()
    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")
    return test_run


@router.post("/{run_id}/cancel", response_model=TestRunResponse)
def cancel_test_run(run_id: str, db: Session = Depends(get_db)):
    """Cancels a queued or currently executing test run."""
    test_run = db.get(TestRun, run_id)
    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")

    if test_run.status in [RunStatus.PASSED.value, RunStatus.FAILED.value, RunStatus.ERROR.value, RunStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel test run with final status '{test_run.status}'",
        )

    test_run.status = RunStatus.CANCELLED.value
    test_run.error_summary = "Test run was cancelled by user"
    db.commit()
    db.refresh(test_run)
    return test_run

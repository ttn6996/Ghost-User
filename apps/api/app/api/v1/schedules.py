"""Schedule management endpoints."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import Schedule, TestCase
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
)

router = APIRouter(prefix="/schedules", tags=["Schedules"])


def calculate_next_run(interval_seconds: Optional[int], cron_expression: Optional[str]) -> datetime:
    """Computes next execution timestamp."""
    now = datetime.now(timezone.utc)
    if interval_seconds:
        return now + timedelta(seconds=interval_seconds)
    # Default fallback: 1 hour if cron parsing is not specified yet
    return now + timedelta(hours=1)


@router.get("", response_model=List[ScheduleResponse])
def list_schedules(
    test_case_id: Optional[str] = Query(None, description="Filter by test case ID"),
    db: Session = Depends(get_db),
):
    query = select(Schedule).order_by(Schedule.created_at.desc())
    if test_case_id:
        query = query.filter(Schedule.test_case_id == test_case_id)
    return db.execute(query).scalars().all()


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, payload.test_case_id)
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{payload.test_case_id}' not found",
        )

    next_run = calculate_next_run(payload.interval_seconds, payload.cron_expression) if payload.enabled else None

    schedule = Schedule(
        test_case_id=payload.test_case_id,
        cron_expression=payload.cron_expression,
        interval_seconds=payload.interval_seconds,
        enabled=payload.enabled,
        next_run_at=next_run,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: str, payload: ScheduleUpdate, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    if payload.cron_expression is not None:
        schedule.cron_expression = payload.cron_expression
    if payload.interval_seconds is not None:
        schedule.interval_seconds = payload.interval_seconds
    if payload.enabled is not None:
        schedule.enabled = payload.enabled
        if schedule.enabled:
            schedule.next_run_at = calculate_next_run(schedule.interval_seconds, schedule.cron_expression)
        else:
            schedule.next_run_at = None

    db.commit()
    db.refresh(schedule)
    return schedule


@router.post("/{schedule_id}/toggle", response_model=ScheduleResponse)
def toggle_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    schedule.enabled = not schedule.enabled
    if schedule.enabled:
        schedule.next_run_at = calculate_next_run(schedule.interval_seconds, schedule.cron_expression)
    else:
        schedule.next_run_at = None

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return None

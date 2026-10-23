"""Automated tests for scheduling, duplicate prevention, and worker recovery."""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun, Schedule
from packages.shared.constants import RunStatus, TriggerType
from apps.worker.scheduler.runner import ScheduleRunner, compute_next_run, ensure_utc
from apps.worker.runner.queue_consumer import QueueConsumer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_startup_recovery_of_interrupted_runs(db_session: Session):
    project = Project(name="Recovery Test", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Interrupted Test",
        definition_json={"name": "Interrupted", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    # Create a simulated crashed run
    orphaned_run = TestRun(
        test_case_id=test_case.id,
        status=RunStatus.RUNNING.value,
        started_at=utc_now() - timedelta(minutes=5),
    )
    db_session.add(orphaned_run)
    db_session.commit()

    runner = ScheduleRunner(db_session)
    recovered = runner.recover_interrupted_runs()

    assert recovered == 1
    db_session.refresh(orphaned_run)
    assert orphaned_run.status == RunStatus.ERROR.value
    assert "interrupted or stopped unexpectedly" in orphaned_run.error_summary
    assert orphaned_run.finished_at is not None


def test_schedule_enqueue_and_advancement(db_session: Session):
    project = Project(name="Schedule Test", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Scheduled Test",
        definition_json={"name": "Scheduled", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    # Schedule due 10 seconds ago
    past_time = utc_now() - timedelta(seconds=10)
    schedule = Schedule(
        test_case_id=test_case.id,
        interval_seconds=300,
        enabled=True,
        next_run_at=past_time,
    )
    db_session.add(schedule)
    db_session.commit()

    runner = ScheduleRunner(db_session)
    enqueued = runner.check_and_enqueue_due_schedules()

    assert enqueued == 1
    db_session.refresh(schedule)
    # Verify next_run_at was advanced into the future
    assert ensure_utc(schedule.next_run_at) > utc_now()
    assert schedule.last_run_at is not None

    # Verify enqueued run exists with trigger_type="schedule"
    runs = db_session.query(TestRun).filter(TestRun.test_case_id == test_case.id).all()
    assert len(runs) == 1
    assert runs[0].status == RunStatus.QUEUED.value
    assert runs[0].trigger_type == TriggerType.SCHEDULE.value


def test_schedule_prevents_duplicate_runs(db_session: Session):
    project = Project(name="Duplicate Check", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Dup Test",
        definition_json={"name": "Dup", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    # Add an already queued run for this test case
    active_run = TestRun(
        test_case_id=test_case.id,
        status=RunStatus.QUEUED.value,
        trigger_type=TriggerType.MANUAL.value,
    )
    db_session.add(active_run)

    # Schedule is also due
    schedule = Schedule(
        test_case_id=test_case.id,
        interval_seconds=60,
        enabled=True,
        next_run_at=utc_now() - timedelta(seconds=5),
    )
    db_session.add(schedule)
    db_session.commit()

    runner = ScheduleRunner(db_session)
    enqueued = runner.check_and_enqueue_due_schedules()

    # Duplicate should be prevented!
    assert enqueued == 0
    runs = db_session.query(TestRun).filter(TestRun.test_case_id == test_case.id).all()
    assert len(runs) == 1  # Only the original run remains

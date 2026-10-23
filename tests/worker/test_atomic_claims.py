"""Automated tests for atomic job claiming, concurrency controls, and failure guarantees."""

import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun
from packages.shared.constants import RunStatus
from apps.worker.runner.queue_consumer import QueueConsumer
from tests.conftest import TestingSessionLocal


def test_atomic_claim_only_one_worker_succeeds(db_session: Session):
    """Verifies that between competing worker sessions, exactly one claims the queued job."""
    project = Project(name="Atomic Project", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Atomic Test Case",
        definition_json={"name": "Atomic", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    # Create two separate DB sessions simulating two worker processes
    session1 = TestingSessionLocal()
    session2 = TestingSessionLocal()

    try:
        consumer1 = QueueConsumer(session1)
        consumer2 = QueueConsumer(session2)

        # Worker 1 claims the job
        claim1 = consumer1.claim_job()
        assert claim1 == run.id

        # Worker 2 attempts to claim the same job concurrently
        claim2 = consumer2.claim_job()
        assert claim2 is None  # Worker 2 must be denied

        # Verify DB status
        db_session.refresh(run)
        assert run.status == RunStatus.RUNNING.value
        assert run.started_at is not None

    finally:
        session1.close()
        session2.close()


def test_concurrent_claim_multi_threaded(db_session: Session):
    """Simulates 5 competing workers attempting to claim a single queued run simultaneously."""
    project = Project(name="Concurrent Project", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Multi Worker Test",
        definition_json={"name": "Multi Worker", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    def worker_claim_attempt():
        session = TestingSessionLocal()
        try:
            consumer = QueueConsumer(session)
            return consumer.claim_job()
        finally:
            session.close()

    # Launch 5 concurrent threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_claim_attempt) for _ in range(5)]
        results = [f.result() for f in futures]

    # Exactly 1 result must be the run.id, and 4 must be None
    successful_claims = [r for r in results if r is not None]
    assert len(successful_claims) == 1
    assert successful_claims[0] == run.id


def test_unhandled_exception_does_not_leave_run_running(db_session: Session):
    """Simulates an engine exception during execution; ensures status transitions to 'error'."""
    project = Project(name="Crash Safety Project", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Crashing Journey",
        definition_json={"name": "Crash", "steps": [{"action": "goto", "url": "/"}]},
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    consumer = QueueConsumer(db_session)
    # Monkeypatch engine.execute_run to simulate a fatal unexpected error
    def crashing_execute(run_id):
        raise RuntimeError("Simulated unhandled execution crash")

    consumer.engine.execute_run = crashing_execute

    processed = consumer.process_next_job()
    assert processed is False

    db_session.refresh(run)
    assert run.status == RunStatus.ERROR.value
    assert "Worker encountered execution failure" in run.error_summary

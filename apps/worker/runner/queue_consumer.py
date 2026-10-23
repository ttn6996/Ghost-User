"""Queue consumer for atomic claiming and dispatching queued test runs."""

import threading
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update, and_

from app.core.config import settings
from app.core.logging import logger
from app.db.models import TestRun
from packages.shared.constants import RunStatus
from apps.worker.runner.engine import BrowserExecutionEngine

# In-process lock to prevent thread-level races on shared connections/cursors
_claim_lock = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QueueConsumer:
    """Manages atomic job claims and dispatching for test execution."""

    def __init__(self, db: Session):
        self.db = db
        self.engine = BrowserExecutionEngine(db)

    def claim_job(self) -> Optional[str]:
        """Atomically claims the oldest queued job using conditional status transition.
        
        Guarantees:
        - Only one worker can transition status from 'queued' to 'running'.
        - Claim is committed to database before browser process launches.
        - Returns run_id if claimed, or None if no jobs available or job claimed by competing worker.
        """
        with _claim_lock:
            # Bounded concurrency: Enforce limit (default 1 active job per worker process)
            running_count = self.db.scalar(
                select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.RUNNING.value)
            ) or 0

            if running_count >= settings.WORKER_CONCURRENCY:
                logger.debug(
                    f"Worker at capacity ({running_count}/{settings.WORKER_CONCURRENCY} active). Waiting for slots."
                )
                return None

            # Find candidate oldest queued job
            candidate_id = self.db.scalar(
                select(TestRun.id)
                .filter(TestRun.status == RunStatus.QUEUED.value)
                .order_by(TestRun.created_at.asc())
                .limit(1)
            )

            if not candidate_id:
                return None

            now = utc_now()
            try:
                # Atomic conditional update: only succeeds if status is still 'queued'
                stmt = (
                    update(TestRun)
                    .where(
                        and_(
                            TestRun.id == candidate_id,
                            TestRun.status == RunStatus.QUEUED.value,
                        )
                    )
                    .values(
                        status=RunStatus.RUNNING.value,
                        started_at=now,
                    )
                )
                result = self.db.execute(stmt)
                self.db.commit()

                if result.rowcount == 1:
                    logger.info(f"Worker atomically claimed test run {candidate_id}")
                    return candidate_id
                else:
                    logger.debug(f"Test run {candidate_id} was claimed by another worker concurrently.")
                    return None

            except Exception as e:
                self.db.rollback()
                logger.warning(f"Failed to claim test run {candidate_id}: {e}")
                return None

    def process_next_job(self) -> bool:
        """Finds, atomically claims, and executes the next job. Returns True if a job was executed."""
        job_id = self.claim_job()
        if not job_id:
            return False

        try:
            self.engine.execute_run(job_id)
            return True
        except Exception as e:
            logger.error(f"Error processing claimed test run {job_id}: {e}", exc_info=True)
            # Ensure job is never left indefinitely in 'running'
            try:
                run = self.db.get(TestRun, job_id)
                if run and run.status == RunStatus.RUNNING.value:
                    run.status = RunStatus.ERROR.value
                    run.finished_at = utc_now()
                    run.error_summary = f"Worker encountered execution failure: {e}"
                    self.db.commit()
            except Exception as persist_err:
                logger.error(f"Failed to persist error state for run {job_id}: {persist_err}")
            return False

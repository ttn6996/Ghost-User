"""Queue consumer for claiming and dispatching queued test runs."""

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.config import settings
from app.core.logging import logger
from app.db.models import TestRun
from packages.shared.constants import RunStatus
from apps.worker.runner.engine import BrowserExecutionEngine


class QueueConsumer:
    def __init__(self, db: Session):
        self.db = db
        self.engine = BrowserExecutionEngine(db)

    def process_next_job(self) -> bool:
        """Finds and executes the next queued job if concurrency limits allow."""
        # Check active running jobs count
        running_count = self.db.scalar(
            select(func.count(TestRun.id)).filter(TestRun.status == RunStatus.RUNNING.value)
        ) or 0

        if running_count >= settings.WORKER_CONCURRENCY:
            logger.debug(
                f"Worker at capacity ({running_count}/{settings.WORKER_CONCURRENCY} active). Waiting for slots."
            )
            return False

        # Find oldest queued job
        queued_run = (
            self.db.execute(
                select(TestRun)
                .filter(TestRun.status == RunStatus.QUEUED.value)
                .order_by(TestRun.created_at.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        if not queued_run:
            return False

        logger.info(f"Worker claimed test run {queued_run.id}. Executing journey...")
        try:
            self.engine.execute_run(queued_run.id)
            return True
        except Exception as e:
            logger.error(f"Error processing test run {queued_run.id}: {e}", exc_info=True)
            return False

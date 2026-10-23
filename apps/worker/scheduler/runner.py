"""Scheduler and reliability manager for recurring tests and restart recovery."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from apscheduler.triggers.cron import CronTrigger

from app.core.logging import logger
from app.db.models import Schedule, TestRun, TestCase
from packages.shared.constants import RunStatus, TriggerType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_next_run(
    interval_seconds: Optional[int],
    cron_expression: Optional[str],
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    base_time = ensure_utc(from_time or utc_now())

    if interval_seconds:
        return base_time + timedelta(seconds=interval_seconds)

    if cron_expression:
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
            next_time = trigger.get_next_fire_time(None, base_time)
            return ensure_utc(next_time)
        except Exception as e:
            logger.warning(f"Could not parse cron expression '{cron_expression}': {e}")
            return base_time + timedelta(hours=1)

    return None


class ScheduleRunner:
    def __init__(self, db: Session):
        self.db = db

    def recover_interrupted_runs(self) -> int:
        """Finds any orphaned runs that were left in 'running' status and marks them as errors."""
        orphans = (
            self.db.execute(
                select(TestRun).filter(TestRun.status == RunStatus.RUNNING.value)
            )
            .scalars()
            .all()
        )

        recovered_count = 0
        for run in orphans:
            logger.warning(f"Recovering orphaned test run {run.id} from interrupted state.")
            now = utc_now()
            run.status = RunStatus.ERROR.value
            run.finished_at = now
            run.error_summary = "Worker was interrupted or stopped unexpectedly while test was executing."
            if run.started_at:
                started = ensure_utc(run.started_at)
                run.duration_ms = int((now - started).total_seconds() * 1000)
            recovered_count += 1

        if recovered_count > 0:
            self.db.commit()
            logger.info(f"Recovered {recovered_count} interrupted test runs.")

        return recovered_count

    def check_and_enqueue_due_schedules(self) -> int:
        """Finds active schedules due for execution and enqueues TestRuns without duplicating active jobs."""
        now = utc_now()

        all_active_schedules = (
            self.db.execute(
                select(Schedule).filter(Schedule.enabled == True)
            )
            .scalars()
            .all()
        )

        enqueued_count = 0
        for sched in all_active_schedules:
            if not sched.next_run_at:
                sched.next_run_at = compute_next_run(sched.interval_seconds, sched.cron_expression, now)
                continue

            sched_next = ensure_utc(sched.next_run_at)
            if sched_next > now:
                continue

            test_case = self.db.get(TestCase, sched.test_case_id)
            if not test_case or not test_case.enabled:
                logger.debug(f"Skipping schedule {sched.id}: Test case not found or disabled.")
                sched.next_run_at = compute_next_run(sched.interval_seconds, sched.cron_expression, now)
                continue

            # Duplicate prevention: Check if already queued or running
            active_run = (
                self.db.execute(
                    select(TestRun).filter(
                        and_(
                            TestRun.test_case_id == sched.test_case_id,
                            TestRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
                        )
                    )
                )
                .scalars()
                .first()
            )

            if active_run:
                logger.info(
                    f"Schedule {sched.id} triggered, but test case {sched.test_case_id} already has active run {active_run.id}. Skipping duplicate."
                )
            else:
                # Enqueue new scheduled test run
                new_run = TestRun(
                    test_case_id=sched.test_case_id,
                    status=RunStatus.QUEUED.value,
                    trigger_type=TriggerType.SCHEDULE.value,
                )
                self.db.add(new_run)
                enqueued_count += 1
                logger.info(f"Enqueued scheduled run for test case {sched.test_case_id}")

            # Update schedule run timestamps
            sched.last_run_at = now
            sched.next_run_at = compute_next_run(sched.interval_seconds, sched.cron_expression, now)

        if all_active_schedules:
            self.db.commit()

        return enqueued_count

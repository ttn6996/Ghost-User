"""Ghost-User background execution worker process."""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# Add project root and apps/api to path if not present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.db.session import SessionLocal
from apps.worker.runner.queue_consumer import QueueConsumer
from apps.worker.scheduler.runner import ScheduleRunner

setup_logging()

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received termination signal ({signum}). Initiating graceful shutdown...")
    running = False


def check_worker_health() -> bool:
    """Verifies worker dependencies and DB connection."""
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        logger.info("Worker health check passed: Database connection verified.")
        return True
    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        return False


def run_worker_loop(poll_interval: float = None, run_once: bool = False):
    global running
    interval = poll_interval or settings.WORKER_POLL_INTERVAL_SECONDS
    logger.info(f"Starting Ghost-User Worker (PID: {os.getpid()}) with poll_interval={interval}s")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Initial health check
    if not check_worker_health():
        logger.error("Initial health check failed. Exiting worker.")
        sys.exit(1)

    # Recovery: Mark any orphaned running jobs as error
    try:
        with SessionLocal() as db:
            ScheduleRunner(db).recover_interrupted_runs()
    except Exception as e:
        logger.error(f"Error during startup recovery: {e}")

    while running:
        try:
            with SessionLocal() as db:
                # 1. Check and enqueue due schedules
                ScheduleRunner(db).check_and_enqueue_due_schedules()

                # 2. Process next queued execution job
                consumer = QueueConsumer(db)
                processed = consumer.process_next_job()
            
            if run_once:
                logger.info("Run-once flag specified. Exiting worker loop.")
                break
                
            if not processed:
                time.sleep(interval)
        except Exception as e:
            logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
            time.sleep(interval)

    logger.info("Worker process terminated gracefully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost-User Test Execution Worker")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    parser.add_argument("--once", action="store_true", help="Run a single polling cycle and exit")
    parser.add_argument("--poll-interval", type=float, default=None, help="Poll interval in seconds")
    args = parser.parse_args()

    if args.health:
        healthy = check_worker_health()
        sys.exit(0 if healthy else 1)
    else:
        run_worker_loop(poll_interval=args.poll_interval, run_once=args.once)

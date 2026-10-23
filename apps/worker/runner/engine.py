"""Playwright Browser Execution Engine for Ghost-User."""

import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import TestRun, TestCase, Project, TestStepResult
from packages.shared.constants import RunStatus, StepStatus
from packages.shared.schemas import TestDefinition
from apps.worker.runner.actions import (
    execute_action,
    StepAssertionFailure,
    StepExecutionError,
)
from apps.worker.runner.artifacts import ArtifactManager
from apps.worker.runner.security import check_browser_request_security, SecurityValidationError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BrowserExecutionEngine:
    def __init__(self, db: Session):
        self.db = db

    def execute_run(self, run_id: str) -> RunStatus:
        """Executes a queued test run end-to-end and persists results."""
        run = self.db.get(TestRun, run_id)
        if not run:
            logger.error(f"Cannot execute non-existent test run '{run_id}'")
            return RunStatus.ERROR

        test_case = self.db.get(TestCase, run.test_case_id)
        if not test_case:
            run.status = RunStatus.ERROR.value
            run.error_summary = "Associated test case not found"
            self.db.commit()
            return RunStatus.ERROR

        project = self.db.get(Project, test_case.project_id)
        if not project:
            run.status = RunStatus.ERROR.value
            run.error_summary = "Associated project not found"
            self.db.commit()
            return RunStatus.ERROR

        # Verify or initialize running timestamp
        start_time = ensure_utc(run.started_at) or utc_now()
        if run.status != RunStatus.RUNNING.value:
            run.status = RunStatus.RUNNING.value
            run.started_at = start_time
            self.db.commit()
            self.db.refresh(run)

        # Parse and validate test definition
        try:
            definition = TestDefinition.model_validate(test_case.definition_json)
        except Exception as e:
            finished_time = utc_now()
            run.status = RunStatus.ERROR.value
            run.finished_at = finished_time
            run.duration_ms = int((finished_time - start_time).total_seconds() * 1000)
            run.error_summary = f"Invalid test definition schema: {e}"
            self.db.commit()
            return RunStatus.ERROR

        artifact_manager = ArtifactManager(run_id=run.id)
        console_logs: List[Dict[str, Any]] = []
        page_errors: List[str] = []
        final_status = RunStatus.PASSED
        error_summary: Optional[str] = None
        trace_rel_path: Optional[str] = None

        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=settings.BROWSER_HEADLESS,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=False,
                )

                if settings.TRACE_ON_FAILURE:
                    context.tracing.start(screenshots=True, snapshots=True, sources=True)

                # Real-time network and navigation security controls
                blocked_events: List[Dict[str, str]] = []

                def handle_route(route):
                    req = route.request
                    url = req.url
                    is_nav = req.is_navigation_request()
                    is_allowed, reason = check_browser_request_security(
                        url=url,
                        base_url=project.base_url,
                        is_navigation=is_nav,
                        allow_local=settings.ALLOW_LOCAL_TARGETS,
                    )
                    if not is_allowed:
                        logger.warning(f"Security policy blocked request: {url} (is_nav={is_nav}, reason={reason})")
                        blocked_events.append({
                            "url": url,
                            "reason": reason,
                            "is_navigation": str(is_nav),
                        })
                        console_logs.append({
                            "type": "error",
                            "text": f"[SECURITY_BLOCKED] {url}: {reason}",
                            "location": None,
                            "timestamp": utc_now().isoformat(),
                        })
                        route.abort("blockedbyclient")
                    else:
                        route.continue_()

                context.route("**/*", handle_route)

                # Also monitor popups or new tabs
                def on_new_page(new_p):
                    new_p.set_default_timeout(settings.ACTION_TIMEOUT_MS)
                context.on("page", on_new_page)

                page = context.new_page()
                page.set_default_timeout(settings.ACTION_TIMEOUT_MS)

                # Collect console errors and page crashes
                def on_console(msg):
                    if msg.type in ("error", "warning"):
                        console_logs.append({
                            "type": msg.type,
                            "text": msg.text,
                            "location": msg.location,
                            "timestamp": utc_now().isoformat(),
                        })

                def on_page_error(exc):
                    page_errors.append(str(exc))

                page.on("console", on_console)
                page.on("pageerror", on_page_error)

                # Execute steps sequentially
                for idx, step_action in enumerate(definition.steps):
                    # Check if cancelled mid-run
                    self.db.refresh(run)
                    if run.status == RunStatus.CANCELLED.value:
                        final_status = RunStatus.CANCELLED
                        error_summary = "Test run cancelled during execution"
                        break

                    step_start = utc_now()
                    step_status = StepStatus.PASSED
                    step_error = None
                    step_screenshot = None

                    try:
                        logger.info(f"Run {run.id} executing step {idx}: {step_action.action}")
                        blocked_before = len(blocked_events)

                        step_screenshot = execute_action(
                            action=step_action,
                            page=page,
                            base_url=project.base_url,
                            step_index=idx,
                            artifact_manager=artifact_manager,
                            allow_local=settings.ALLOW_LOCAL_TARGETS,
                        )

                        # Verify no navigations were blocked during this step
                        new_blocked = blocked_events[blocked_before:]
                        nav_blocked = [b for b in new_blocked if b["is_navigation"] == "True"]
                        if nav_blocked:
                            raise StepExecutionError(f"Security policy blocked navigation: {nav_blocked[0]['reason']}")

                        # Also verify page.url is still on authorized origin
                        if page.url and page.url != "about:blank":
                            url_ok, reason = check_browser_request_security(
                                page.url,
                                base_url=project.base_url,
                                is_navigation=True,
                                allow_local=settings.ALLOW_LOCAL_TARGETS,
                            )
                            if not url_ok:
                                raise StepExecutionError(f"Security violation: Page is at disallowed location '{page.url}': {reason}")

                    except StepAssertionFailure as e:
                        step_status = StepStatus.FAILED
                        step_error = str(e)
                        final_status = RunStatus.FAILED
                        error_summary = f"Assertion failure at step {idx} ({step_action.action}): {e}"
                        # Capture failure screenshot
                        try:
                            f_abs, f_rel = artifact_manager.get_screenshot_path(idx, "failure")
                            page.screenshot(path=str(f_abs), full_page=True)
                            step_screenshot = f_rel
                        except Exception as shot_err:
                            logger.warning(f"Could not capture failure screenshot: {shot_err}")
                    except StepExecutionError as e:
                        step_status = StepStatus.ERROR
                        step_error = str(e)
                        final_status = RunStatus.ERROR
                        error_summary = f"Execution error at step {idx} ({step_action.action}): {e}"
                        # Capture failure screenshot
                        try:
                            f_abs, f_rel = artifact_manager.get_screenshot_path(idx, "error")
                            page.screenshot(path=str(f_abs), full_page=True)
                            step_screenshot = f_rel
                        except Exception as shot_err:
                            logger.warning(f"Could not capture error screenshot: {shot_err}")
                    except Exception as e:
                        step_status = StepStatus.ERROR
                        step_error = f"Unhandled exception: {e}"
                        final_status = RunStatus.ERROR
                        error_summary = f"Unexpected failure at step {idx}: {e}"

                    step_end = utc_now()
                    duration = int((step_end - step_start).total_seconds() * 1000)

                    # Persist step result
                    step_record = TestStepResult(
                        test_run_id=run.id,
                        step_index=idx,
                        action=step_action.action,
                        status=step_status.value,
                        started_at=step_start,
                        finished_at=step_end,
                        duration_ms=duration,
                        error_message=step_error,
                        screenshot_path=step_screenshot,
                    )
                    self.db.add(step_record)
                    self.db.commit()

                    if step_status in (StepStatus.FAILED, StepStatus.ERROR):
                        # Stop execution on first failure/error
                        break

                # Save trace if run failed or had errors
                if final_status in (RunStatus.FAILED, RunStatus.ERROR) and settings.TRACE_ON_FAILURE:
                    try:
                        trace_abs, trace_rel = artifact_manager.get_trace_path()
                        context.tracing.stop(path=str(trace_abs))
                        trace_rel_path = trace_rel
                    except Exception as trace_err:
                        logger.warning(f"Failed to save Playwright trace: {trace_err}")
                elif settings.TRACE_ON_FAILURE and context:
                    try:
                        context.tracing.stop()
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Fatal browser crash or launch failure for run {run.id}: {e}", exc_info=True)
            final_status = RunStatus.ERROR
            error_summary = f"Browser infrastructure error: {e}"

        finally:
            # Safe resource teardown
            try:
                if page and not page.is_closed():
                    page.close()
            except Exception:
                pass
            try:
                if context:
                    context.close()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass

        # Update final run record
        finished_time = utc_now()
        total_duration = int((finished_time - start_time).total_seconds() * 1000)

        run.status = final_status.value
        run.finished_at = finished_time
        run.duration_ms = total_duration
        run.error_summary = error_summary
        run.console_logs_json = console_logs
        run.page_errors_json = page_errors
        run.trace_path = trace_rel_path

        self.db.commit()
        self.db.refresh(run)
        logger.info(f"Run {run.id} finished with status '{final_status.value}' in {total_duration}ms")
        return final_status

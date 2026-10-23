"""Automated tests for Playwright browser execution engine and actions."""

import os
import pytest
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun, TestStepResult
from packages.shared.constants import RunStatus, StepStatus
from apps.worker.runner.engine import BrowserExecutionEngine
from tests.fixtures.server import start_fixture_server_in_background, PORT


@pytest.fixture(scope="module")
def fixture_server():
    server = start_fixture_server_in_background(port=PORT)
    yield f"http://127.0.0.1:{PORT}"
    server.shutdown()


def test_successful_browser_journey(db_session: Session, fixture_server: str, tmp_path):
    # Set artifact storage to temporary directory
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    # 1. Create project
    project = Project(
        name="Fixture Website",
        base_url=fixture_server,
        description="Local deterministic test site",
    )
    db_session.add(project)
    db_session.commit()

    # 2. Create test case with all common actions
    test_case = TestCase(
        project_id=project.id,
        name="Full User Journey",
        definition_json={
            "name": "Full User Journey",
            "steps": [
                {"action": "goto", "url": "/"},
                {"action": "assert_visible", "selector": "h1"},
                {"action": "assert_text", "selector": "#description", "expected_text": "deterministic test environment"},
                {"action": "click", "selector": "#nav-login"},
                {"action": "assert_url", "expected_url": "/login"},
                {"action": "fill", "selector": "#email", "value": "alice@example.com"},
                {"action": "select_option", "selector": "#role", "value": "admin"},
                {"action": "check", "selector": "#terms"},
                {"action": "screenshot", "name": "login_filled"},
                {"action": "click", "selector": "#login-btn"},
                {"action": "assert_url", "expected_url": "/dashboard"},
                {"action": "assert_visible", "selector": "#welcome-banner"},
                {"action": "assert_text", "selector": "#welcome-banner", "expected_text": "Authentication Successful"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    # 3. Create test run
    test_run = TestRun(
        test_case_id=test_case.id,
        status=RunStatus.QUEUED.value,
    )
    db_session.add(test_run)
    db_session.commit()

    # 4. Execute using BrowserExecutionEngine
    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(test_run.id)

    # 5. Verify results
    assert status == RunStatus.PASSED
    db_session.refresh(test_run)
    assert test_run.status == RunStatus.PASSED.value
    assert test_run.duration_ms > 0
    assert test_run.started_at is not None
    assert test_run.finished_at is not None
    assert test_run.error_summary is None

    # Verify steps
    steps = db_session.query(TestStepResult).filter(TestStepResult.test_run_id == test_run.id).order_by(TestStepResult.step_index).all()
    assert len(steps) == 13
    for step in steps:
        assert step.status == StepStatus.PASSED.value
        assert step.duration_ms >= 0

    # Verify screenshot was captured
    screenshot_step = steps[8]
    assert screenshot_step.action == "screenshot"
    assert screenshot_step.screenshot_path is not None
    abs_screenshot = tmp_path / screenshot_step.screenshot_path
    assert abs_screenshot.exists()


def test_assertion_failure_journey(db_session: Session, fixture_server: str, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    project = Project(name="Fixture Site Fail", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Failing Assertion Journey",
        definition_json={
            "name": "Failing Assertion Journey",
            "steps": [
                {"action": "goto", "url": "/"},
                {"action": "assert_text", "selector": "h1", "expected_text": "NONEXISTENT_HEADER_TEXT"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    test_run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(test_run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(test_run.id)

    assert status == RunStatus.FAILED
    db_session.refresh(test_run)
    assert test_run.status == RunStatus.FAILED.value
    assert "Assertion failure" in test_run.error_summary
    assert test_run.trace_path is not None  # Trace was preserved on failure

    steps = db_session.query(TestStepResult).filter(TestStepResult.test_run_id == test_run.id).order_by(TestStepResult.step_index).all()
    assert len(steps) == 2
    assert steps[0].status == StepStatus.PASSED.value
    assert steps[1].status == StepStatus.FAILED.value
    assert steps[1].error_message is not None
    # Verify failure screenshot was saved
    assert steps[1].screenshot_path is not None
    assert (tmp_path / steps[1].screenshot_path).exists()


def test_console_and_page_error_capture(db_session: Session, fixture_server: str, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    project = Project(name="Broken Page Test", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Broken Page Error Capture",
        definition_json={
            "name": "Broken Page Error Capture",
            "steps": [
                {"action": "goto", "url": "/broken"},
                {"action": "wait_for_visible", "selector": "h1"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    test_run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(test_run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(test_run.id)

    db_session.refresh(test_run)
    # Check that console logs and unhandled page exceptions were captured
    assert test_run.console_logs_json is not None
    assert len(test_run.console_logs_json) > 0
    assert any("simulated frontend error" in log["text"].lower() for log in test_run.console_logs_json)

    assert test_run.page_errors_json is not None
    assert len(test_run.page_errors_json) > 0
    assert any("simulated unhandled exception" in err.lower() for err in test_run.page_errors_json)

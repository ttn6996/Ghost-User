"""Deterministic browser network security and request interception tests."""

import os
import pytest
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun, TestStepResult
from packages.shared.constants import RunStatus, StepStatus
from apps.worker.runner.engine import BrowserExecutionEngine
from apps.worker.runner.security import (
    resolve_target_url,
    resolve_and_validate_host,
    check_browser_request_security,
    SecurityValidationError,
)
from tests.fixtures.server import start_fixture_server_in_background, PORT


@pytest.fixture(scope="module")
def fixture_server():
    server = start_fixture_server_in_background(port=0)
    actual_port = server.server_address[1]
    yield f"http://127.0.0.1:{actual_port}"
    server.shutdown()
    server.server_close()


def test_valid_same_origin_navigation(db_session: Session, fixture_server: str):
    """1. Valid same-origin navigation should succeed completely."""
    project = Project(name="Same Origin Project", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Valid Same Origin Test",
        definition_json={
            "name": "Same Origin",
            "steps": [
                {"action": "goto", "url": "/"},
                {"action": "assert_visible", "selector": "h1"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)
    assert status == RunStatus.PASSED


def test_explicit_external_goto_blocked(db_session: Session, fixture_server: str):
    """2. Explicit external goto step must be blocked before execution."""
    project = Project(name="Origin Guard Project", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="External Goto",
        definition_json={
            "name": "External Goto",
            "steps": [
                {"action": "goto", "url": "https://malicious-external-site.com/steal"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)
    assert status == RunStatus.ERROR

    db_session.refresh(run)
    assert "Security validation violation" in run.error_summary or "does not match base origin" in run.error_summary


def test_click_navigating_to_external_origin_blocked(db_session: Session, fixture_server: str):
    """3. Clicking a link that navigates to an external origin must be blocked by request controls."""
    project = Project(name="Click External Guard", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Click External Link",
        definition_json={
            "name": "Click External Link",
            "steps": [
                {"action": "goto", "url": "/external-link"},
                {"action": "click", "selector": "#ext-link"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)
    assert status == RunStatus.ERROR

    db_session.refresh(run)
    assert "Security policy blocked navigation" in run.error_summary or "Navigation out-of-bounds" in run.error_summary


def test_popup_navigating_to_external_origin_blocked(db_session: Session, fixture_server: str):
    """3b. Clicking a link that opens a popup to an external origin must be blocked."""
    project = Project(name="Popup Guard Project", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Popup External Link",
        definition_json={
            "name": "Popup External Link",
            "steps": [
                {"action": "goto", "url": "/popup-external"},
                {"action": "click", "selector": "#popup-link"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)
    assert status == RunStatus.ERROR

    db_session.refresh(run)
    assert "Security policy blocked navigation" in run.error_summary or "Popup destination blocked" in run.error_summary


def test_redirect_to_blocked_destination_blocked(db_session: Session, fixture_server: str):
    """4. HTTP redirect to a blocked metadata/private destination must be aborted."""
    project = Project(name="Redirect Guard", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Redirect to Metadata",
        definition_json={
            "name": "Redirect to Metadata",
            "steps": [
                {"action": "goto", "url": "/redirect-to-metadata", "timeout_ms": 2000},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)
    assert status == RunStatus.ERROR


def test_page_subresource_request_to_metadata_ip_blocked(db_session: Session, fixture_server: str):
    """5. Page subresource requests (img, fetch) to metadata IP must be blocked and logged."""
    project = Project(name="Subresource Guard", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Metadata Subresource",
        definition_json={
            "name": "Metadata Subresource",
            "steps": [
                {"action": "goto", "url": "/metadata-subresource"},
                {"action": "wait_for_visible", "selector": "h1"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    engine = BrowserExecutionEngine(db_session)
    status = engine.execute_run(run.id)

    db_session.refresh(run)
    # Step itself renders h1, but console logs should show the blocked subresources!
    assert run.console_logs_json is not None
    assert any("SECURITY_BLOCKED" in log["text"] and "169.254.169.254" in log["text"] for log in run.console_logs_json)


def test_hostname_resolving_to_blocked_ip():
    """6. Hostname resolving to a blocked IP must raise SecurityValidationError."""
    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_and_validate_host("169.254.169.254", allow_local=False)

    with pytest.raises(SecurityValidationError, match="loopback"):
        resolve_and_validate_host("127.0.0.1", allow_local=False)

    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_and_validate_host("10.0.0.1", allow_local=False)

    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_and_validate_host("192.168.1.1", allow_local=False)


def test_production_mode_never_allows_local():
    """7. Production mode must reject localhost even if allow_local is requested."""
    # Temporarily force environment to production
    from app.core.config import settings
    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        with pytest.raises(SecurityValidationError, match="loopback"):
            resolve_target_url("/test", "http://127.0.0.1:8899", allow_local=True)
    finally:
        settings.ENVIRONMENT = original_env

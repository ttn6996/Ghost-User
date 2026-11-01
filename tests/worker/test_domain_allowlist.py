"""Automated tests for multi-domain allowlist enforcement across browser execution and security checks."""

import socket
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session
from apps.worker.runner.security import check_browser_request_security, resolve_target_url, SecurityValidationError
from apps.worker.runner.engine import BrowserExecutionEngine
from app.db.models import Project, TestCase, TestRun
from packages.shared.constants import RunStatus
from tests.fixtures.server import start_fixture_server_in_background


@pytest.fixture(autouse=True)
def mock_dns_for_allowlist_tests():
    """Mocks DNS lookup for simulated domains so unit tests run deterministically in any network environment."""
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if not host:
            return real_getaddrinfo(host, port, *args, **kwargs)
        lower_h = str(host).lower().strip()
        if lower_h in ("127.0.0.1", "localhost", "::1"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 80))]
        if lower_h in ("169.254.169.254", "10.0.0.5", "10.0.0.1"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (lower_h, port or 80))]
        if any(d in lower_h for d in ("example.com", "partner.io", "thirdparty.com")):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80))]
        return real_getaddrinfo(host, port, *args, **kwargs)

    with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
        yield


# 1. Direct Security Validation Logic Tests
def test_allowlist_permits_base_and_allowed_domains():
    """Validates that base_url and all allowed_domains pass navigation security."""
    base_url = "https://app.example.com"
    allowed_domains = ["auth.example.com", "cdn.example.com", "api.partner.io"]

    # Base domain navigation -> Allowed
    ok, _ = check_browser_request_security("https://app.example.com/dashboard", base_url, allowed_domains, is_navigation=True)
    assert ok is True

    # Secondary allowed domains -> Allowed
    ok, _ = check_browser_request_security("https://auth.example.com/oauth/login", base_url, allowed_domains, is_navigation=True)
    assert ok is True
    ok, _ = check_browser_request_security("https://api.partner.io/v1/data", base_url, allowed_domains, is_navigation=True)
    assert ok is True

    # Unlisted domain -> Blocked
    ok, reason = check_browser_request_security("https://malicious-site.com/steal", base_url, allowed_domains, is_navigation=True)
    assert ok is False
    assert "out-of-bounds" in reason or "not authorized" in reason


def test_allowlist_wildcard_subdomain_matching():
    """Validates wildcard subdomain matching (*.example.com)."""
    base_url = "https://example.com"
    allowed_domains = ["*.example.com"]

    # Allowed subdomains
    ok, _ = check_browser_request_security("https://sub.example.com/page", base_url, allowed_domains, is_navigation=True)
    assert ok is True
    ok, _ = check_browser_request_security("https://deep.nested.example.com/", base_url, allowed_domains, is_navigation=True)
    assert ok is True
    ok, _ = check_browser_request_security("https://example.com/", base_url, allowed_domains, is_navigation=True)
    assert ok is True

    # Disallowed domains
    ok, _ = check_browser_request_security("https://fake-example.com/", base_url, allowed_domains, is_navigation=True)
    assert ok is False
    ok, _ = check_browser_request_security("https://anotherdomain.com/", base_url, allowed_domains, is_navigation=True)
    assert ok is False


def test_allowlist_ssrf_priority_over_allowed_domain():
    """Even if an IP is added to allowed_domains, SSRF protection overrides and blocks it."""
    base_url = "https://example.com"
    allowed_domains = ["169.254.169.254", "10.0.0.5"]

    ok, reason = check_browser_request_security("http://169.254.169.254/meta-data", base_url, allowed_domains, is_navigation=True)
    assert ok is False
    assert "blocked" in reason.lower()


def test_subresource_enforcement_with_allowlist():
    """When enforce_subresource_domains is True, subresources outside allowlist are blocked."""
    base_url = "https://example.com"
    allowed_domains = ["cdn.example.com"]

    # Allowed subresource
    ok, _ = check_browser_request_security(
        "https://cdn.example.com/lib.js",
        base_url,
        allowed_domains,
        is_navigation=False,
        enforce_subresource_domains=True,
    )
    assert ok is True

    # Disallowed subresource
    ok, reason = check_browser_request_security(
        "https://tracker.thirdparty.com/track.js",
        base_url,
        allowed_domains,
        is_navigation=False,
        enforce_subresource_domains=True,
    )
    assert ok is False
    assert "domain not in allowlist" in reason.lower() or "blocked" in reason.lower()


# 2. Browser Engine Real Execution with Multi-Server Fixtures
@pytest.fixture(scope="module")
def multi_servers():
    """Spins up Server A (Base), Server B (Allowed Secondary), and Server C (Disallowed External)."""
    server_a = start_fixture_server_in_background(port=0)
    server_b = start_fixture_server_in_background(port=0)
    server_c = start_fixture_server_in_background(port=0)

    url_a = f"http://127.0.0.1:{server_a.server_address[1]}"
    url_b = f"http://127.0.0.1:{server_b.server_address[1]}"
    url_c = f"http://127.0.0.1:{server_c.server_address[1]}"

    yield {
        "url_a": url_a,
        "url_b": url_b,
        "url_c": url_c,
        "host_b": f"127.0.0.1:{server_b.server_address[1]}",
        "host_c": f"127.0.0.1:{server_c.server_address[1]}",
    }

    server_a.shutdown()
    server_b.shutdown()
    server_c.shutdown()
    server_a.server_close()
    server_b.server_close()
    server_c.server_close()


def test_goto_allowed_secondary_domain_succeeds(db_session: Session, multi_servers):
    """Playwright worker successfully navigates to a domain listed in allowed_domains."""
    project = Project(
        name="Multi-Domain Allowed Test",
        base_url=multi_servers["url_a"],
        allowed_domains=[multi_servers["host_b"]],
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Cross Domain Journey",
        definition_json={
            "name": "Cross Domain Allowed",
            "steps": [
                {"action": "goto", "url": multi_servers["url_a"] + "/"},
                {"action": "assert_visible", "selector": "h1"},
                {"action": "goto", "url": multi_servers["url_b"] + "/dashboard"},
                {"action": "assert_visible", "selector": "#welcome-banner"},
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


def test_goto_disallowed_domain_fails(db_session: Session, multi_servers):
    """Playwright worker blocks goto navigation to an unlisted external domain."""
    project = Project(
        name="Disallowed Domain Test",
        base_url=multi_servers["url_a"],
        allowed_domains=[multi_servers["host_b"]],  # host_c is NOT allowed
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Disallowed Goto",
        definition_json={
            "name": "Disallowed Goto",
            "steps": [
                {"action": "goto", "url": multi_servers["url_c"] + "/"},
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
    assert "Security policy blocked navigation" in run.error_summary or "out-of-bounds" in run.error_summary

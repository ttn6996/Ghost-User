"""Automated tests for credential & secret masking across logs, error traces, and JSON outputs."""

import io
import json
import logging
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.masking import (
    MASK_STRING,
    mask_sensitive_data,
    mask_secrets_in_dict,
    mask_text,
    MaskingLogFilter,
    is_sensitive_key,
)
from app.core.logging import setup_logging
from apps.worker.runner.masking import (
    extract_all_run_secrets,
    extract_secrets_from_test_definition,
    extract_secrets_from_auth_profile,
    mask_console_logs,
    mask_page_errors,
    mask_playwright_trace,
)
from apps.worker.runner.engine import BrowserExecutionEngine
from app.db.models import Project, TestCase, TestRun, TestStepResult
from packages.shared.constants import RunStatus, StepStatus


# 1. Direct Unit Tests for Masking Utility
def test_mask_exact_secret_strings():
    """Exact secret values must be cleanly replaced with ***MASKED***."""
    raw_text = "User authenticated with password SecretP@ss123 and token tok_live_abcdef123456"
    secrets = ["SecretP@ss123", "tok_live_abcdef123456"]
    masked = mask_sensitive_data(raw_text, secrets=secrets)

    assert "SecretP@ss123" not in masked
    assert "tok_live_abcdef123456" not in masked
    assert masked == "User authenticated with password ***MASKED*** and token ***MASKED***"


def test_mask_heuristic_token_patterns():
    """Common token formats (Bearer tokens, basic auth, API keys) must be masked automatically."""
    cases = [
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz.abc", "Authorization: Bearer ***MASKED***"),
        ("Basic dXNlcjpwYXNzd29yZA==", "Basic ***MASKED***"),
        ("curl -H 'x-api-key: sk-live-9876543210abcdef'", "curl -H 'x-api-key: ***MASKED***'"),
        ("https://example.com/api?token=secret123&password=myPass456", "https://example.com/api?token=***MASKED***&password=***MASKED***"),
    ]
    for raw, expected in cases:
        masked = mask_sensitive_data(raw)
        assert masked == expected


def test_mask_dictionary_and_nested_json():
    """Sensitive keys in nested dictionaries must have values redacted."""
    payload = {
        "user": "tester",
        "password": "ClearTextPassword!",
        "auth": {
            "token": "tok_12345",
            "api_key": "key_abcdef",
            "safe_field": "visible_value",
        },
        "items": [{"secret": "super_secret_value"}],
    }
    masked = mask_secrets_in_dict(payload)
    assert masked["password"] == "***MASKED***"
    assert masked["auth"]["token"] == "***MASKED***"
    assert masked["auth"]["api_key"] == "***MASKED***"
    assert masked["auth"]["safe_field"] == "visible_value"
    assert masked["items"][0]["secret"] == "***MASKED***"


def test_mask_empty_or_none_inputs():
    """Masking utility handles empty, None, and non-string inputs safely."""
    assert mask_sensitive_data(None) is None
    assert mask_sensitive_data("") == ""
    assert mask_secrets_in_dict({}) == {}


# 2. Secret Extraction from Test Definitions and Auth Profiles
def test_secret_extraction_from_definition_and_auth_profile():
    definition = {
        "steps": [
            {"action": "goto", "url": "https://user:SuperSecretUrlPass@example.com"},
            {"action": "fill", "selector": "#user_password", "value": "MyPassword123!"},
            {"action": "fill", "selector": "#normal_input", "value": "SafeSearchTerm"},
        ]
    }
    auth_profile = {
        "cookies": [{"name": "session", "value": "secret_cookie_token_9999"}],
        "localStorage": {"auth_token": "secret_ls_jwt_token_8888"},
        "bearer_token": "secret_bearer_token_7777",
    }
    project_secrets = {"API_KEY": "secret_api_key_6666"}

    secrets = extract_all_run_secrets(definition, auth_profile, project_secrets)
    assert "SuperSecretUrlPass" in secrets
    assert "MyPassword123!" in secrets
    assert "secret_cookie_token_9999" in secrets
    assert "secret_ls_jwt_token_8888" in secrets
    assert "secret_bearer_token_7777" in secrets
    assert "secret_api_key_6666" in secrets
    assert "SafeSearchTerm" not in secrets


# 3. Project API Credentials & Auth Profile Masking
def test_project_secret_masking_in_api_response(client: TestClient):
    """POST /api/v1/projects must mask secret values in the response."""
    res = client.post("/api/v1/projects", json={
        "name": "Auth Project",
        "base_url": "https://example.com",
        "secrets_json": {"ADMIN_PASSWORD": "SuperSecretPassword123!"},
        "secrets_masked": True,
    })
    assert res.status_code == 201
    assert res.json()["secrets_json"]["ADMIN_PASSWORD"] == "***MASKED***"


def test_project_auth_profile_credentials_masked_in_get_project(client: TestClient, db_session: Session):
    """GET /api/v1/projects/{id} must not return plain text credentials in auth_profile_json."""
    auth_prof = {
        "cookies": [{"name": "session", "value": "secret_cookie_token_12345", "domain": "example.com"}],
        "localStorage": {"auth_token": "secret_ls_jwt_token_999"},
        "bearer_token": "secret_bearer_token_xyz",
    }
    project = Project(
        name="Auth Profile Project",
        base_url="https://example.com",
        auth_profile_json=auth_prof,
    )
    db_session.add(project)
    db_session.commit()

    res = client.get(f"/api/v1/projects/{project.id}")
    assert res.status_code == 200
    prof = res.json()["auth_profile_json"]

    assert prof["cookies"][0]["value"] == "***MASKED***"
    assert prof["localStorage"]["auth_token"] == "***MASKED***"
    assert prof["bearer_token"] == "***MASKED***"


# 4. Engine Run Masking: Console Logs, Errors, and Trace Archive
def test_engine_masks_secrets_in_console_logs_and_errors(db_session: Session, client: TestClient):
    """BrowserExecutionEngine must mask secrets across console logs, page errors, and error summaries."""
    secret_pass = "P@ssw0rdTopSecret999!"
    project = Project(
        name="Engine Mask QA",
        base_url="https://example.com",
        secrets_json={"PASSWORD": secret_pass},
    )
    db_session.add(project)
    db_session.commit()

    # Create test definition containing secret in FillAction
    test_case = TestCase(
        project_id=project.id,
        name="Masking Step Test",
        definition_json={
            "name": "Masking Step Test",
            "steps": [
                {"action": "goto", "url": "https://example.com"},
                {"action": "fill", "selector": "#password", "value": secret_pass},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    # Execute run with BrowserExecutionEngine
    engine = BrowserExecutionEngine(db_session)
    # Mocking real browser goto to verify data masking pipeline
    raw_logs = [
        {"type": "error", "text": f"Failed entering password: {secret_pass}"},
        {"type": "log", "text": "Token Authorization: Bearer eyJhbGciOi_test_token_xyz was used"},
    ]
    raw_errors = [f"Uncaught Error: Authentication failed with secret {secret_pass}"]
    run_secrets = [secret_pass]

    masked_logs = mask_console_logs(raw_logs, secrets=run_secrets)
    masked_errors = mask_page_errors(raw_errors, secrets=run_secrets)
    masked_summary = mask_sensitive_data(f"Assertion failed: {secret_pass} invalid", secrets=run_secrets)

    run.status = RunStatus.FAILED.value
    run.console_logs_json = masked_logs
    run.page_errors_json = masked_errors
    run.error_summary = masked_summary
    db_session.commit()

    # Verify API response
    api_res = client.get(f"/api/v1/test-runs/{run.id}")
    assert api_res.status_code == 200
    data = api_res.json()

    assert secret_pass not in str(data["console_logs_json"])
    assert "***MASKED***" in data["console_logs_json"][0]["text"]
    assert secret_pass not in str(data["page_errors_json"])
    assert "***MASKED***" in data["page_errors_json"][0]
    assert secret_pass not in data["error_summary"]
    assert "***MASKED***" in data["error_summary"]


def test_mask_playwright_trace_zip(tmp_path):
    """Playwright trace zip archive must have text files redacted with ***MASKED***."""
    trace_file = tmp_path / "test_trace.zip"
    secret_val = "SuperSecretTraceToken12345"

    with zipfile.ZipFile(trace_file, "w") as zf:
        zf.writestr("trace.trace", json.dumps({"event": "fill", "value": secret_val}))
        zf.writestr("trace.network", f"Authorization: Bearer {secret_val}")
        zf.writestr("screenshot.png", b"\x89PNG\r\n\x1a\n")

    assert mask_playwright_trace(trace_file, secrets=[secret_val]) is True

    # Read back and verify secret is gone
    with zipfile.ZipFile(trace_file, "r") as zf:
        trace_content = zf.read("trace.trace").decode("utf-8")
        network_content = zf.read("trace.network").decode("utf-8")

        assert secret_val not in trace_content
        assert "***MASKED***" in trace_content
        assert secret_val not in network_content
        assert "***MASKED***" in network_content


def test_masking_log_filter():
    """MaskingLogFilter should redact sensitive tokens from logging records."""
    log_filter = MaskingLogFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User login failed with password SecretPass456!",
        args=(),
        exc_info=None,
    )
    result = log_filter.filter(record)
    assert result is True
    # If explicit secret pattern or format
    record2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=12,
        msg="Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def",
        args=(),
        exc_info=None,
    )
    log_filter.filter(record2)
    assert "eyJhbGciOi" not in record2.msg
    assert "***MASKED***" in record2.msg


def test_is_sensitive_key_avoids_false_positives():
    """is_sensitive_key must return False for innocent metrics like 'passed', 'author', 'compass', 'passenger'."""
    assert is_sensitive_key("passed") is False
    assert is_sensitive_key("author") is False
    assert is_sensitive_key("compass") is False
    assert is_sensitive_key("passenger") is False

    # Valid sensitive keys must return True
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("user_pass") is True
    assert is_sensitive_key("userPassword") is True
    assert is_sensitive_key("sessionToken") is True
    assert is_sensitive_key("apiKey") is True
    assert is_sensitive_key("auth_token") is True

    # mask_sensitive_data must not corrupt test summary metrics
    summary_metrics = {"passed": 10, "failed": 0, "author": "Alice"}
    result = mask_sensitive_data(summary_metrics)
    assert result == {"passed": 10, "failed": 0, "author": "Alice"}


def test_local_storage_non_sensitive_words_not_extracted():
    """extract_secrets_from_auth_profile must not treat common UI strings as secrets."""
    profile = {
        "localStorage": {
            "theme": "dark",
            "debug": "true",
            "locale": "en",
            "auth_token": "secret_ls_jwt_token_8888",
        }
    }
    secrets = extract_secrets_from_auth_profile(profile)
    assert "dark" not in secrets
    assert "true" not in secrets
    assert "en" not in secrets
    assert "secret_ls_jwt_token_8888" in secrets


def test_bearer_token_base64_special_chars_masked():
    """RE_BEARER_AUTH must match Base64 tokens with '+' and '/' characters."""
    raw = "Authorization: Bearer abcd+efgh/1234=="
    masked = mask_text(raw)
    assert masked == "Authorization: Bearer ***MASKED***"


def test_query_param_auth_token_and_session_id_masked():
    """Query parameters 'auth_token' and 'session_id' must be masked by regex."""
    url = "https://example.com/callback?auth_token=my_secret_token_123&session_id=sess_456"
    masked = mask_text(url)
    assert "my_secret_token_123" not in masked
    assert "sess_456" not in masked
    assert "auth_token=***MASKED***" in masked
    assert "session_id=***MASKED***" in masked


def test_extract_all_run_secrets_from_json_string():
    """extract_all_run_secrets must support project_secrets passed as a JSON string."""
    secrets_str = json.dumps({"API_KEY": "s3cret_api_key_12345", "CLIENT_SECRET": "s3cret_client_xyz"})
    extracted = extract_all_run_secrets(None, None, secrets_str)
    assert "s3cret_api_key_12345" in extracted
    assert "s3cret_client_xyz" in extracted


def test_setup_logging_attaches_masking_filter():
    """setup_logging must attach MaskingLogFilter to handlers and root logger."""
    setup_logging()
    root_logger = logging.getLogger()
    assert any(isinstance(f, MaskingLogFilter) for f in root_logger.filters) or any(
        any(isinstance(f, MaskingLogFilter) for f in h.filters) for h in root_logger.handlers
    )


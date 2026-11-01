"""Adversarial stress-testing suite for credential masking, trace sanitization, and auth profile scrubbing."""

import json
import os
import shutil
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.masking import (
    MASK_STRING,
    mask_sensitive_data,
    mask_secrets_in_dict,
    mask_text,
    MaskingLogFilter,
)
from apps.worker.runner.masking import (
    extract_all_run_secrets,
    extract_secrets_from_auth_profile,
    extract_secrets_from_test_definition,
    mask_console_logs,
    mask_page_errors,
    mask_playwright_trace,
)
from app.db.models import Project, TestCase, TestRun
from app.schemas.project import ProjectResponse
from packages.shared.constants import RunStatus
from packages.shared.schemas import FillAction, GotoAction, TestDefinition


# =====================================================================
# Group 1: URL Encoding, Complex URLs, and Parameter Variations
# =====================================================================

def test_adversarial_url_encoded_secrets_with_special_characters():
    """Adversarial challenge: Secrets containing special characters (@, +, =, &, #, !)
    when URL-encoded in request URLs, query strings, or error traces."""
    secret = "P@ss+w0rd=99#!"
    quoted_secret = urllib.parse.quote(secret)
    quoted_plus_secret = urllib.parse.quote_plus(secret)

    # In HTTP logs / traces, URLs often contain percent-encoded secrets
    trace_log = f"GET /api/login?custom_param={quoted_secret} HTTP/1.1"
    masked = mask_text(trace_log, secrets=[secret])

    # Plaintext or percent-encoded secret must NOT survive
    assert quoted_secret not in masked, f"URL-encoded secret leaked: {masked}"
    assert secret not in masked, f"Plaintext secret leaked: {masked}"
    assert MASK_STRING in masked


def test_adversarial_url_encoded_lowercase_hex_secrets():
    """Adversarial challenge: Percent-encoded secrets with lowercase hex (e.g. %40 vs %4a)."""
    secret = "Key@2026/Alpha"
    # standard quote produces uppercase %40 and %2F
    encoded_lower = urllib.parse.quote(secret).replace("%40", "%40").replace("%2F", "%2f")

    log_entry = f"Redirected to /auth?signature={encoded_lower}"
    masked = mask_text(log_entry, secrets=[secret])

    assert encoded_lower not in masked, f"Lowercase hex URL-encoded secret leaked: {masked}"
    assert MASK_STRING in masked


def test_adversarial_non_standard_query_parameter_names():
    """Adversarial challenge: Query parameters using auth keywords not in standard heuristic list
    (e.g. ?session=..., ?client_secret=..., ?auth_token=..., ?sig=...)."""
    secret = "MySuperSecretValue123"
    test_urls = [
        f"https://example.com/callback?session={secret}",
        f"https://example.com/oauth?client_secret={secret}",
        f"https://example.com/api?auth_token={secret}",
        f"https://example.com/auth?sig={secret}",
    ]
    for url in test_urls:
        masked = mask_text(url, secrets=[secret])
        assert secret not in masked, f"Secret leaked in URL {url}: {masked}"


def test_adversarial_secret_in_url_path_segments():
    """Adversarial challenge: Secret embedded in URL path segment instead of query param."""
    secret = "session_token_xyz987"
    path_url = f"https://example.com/api/v1/sessions/{secret}/validate"
    masked = mask_text(path_url, secrets=[secret])
    assert secret not in masked, f"Secret leaked in URL path: {masked}"
    assert f"https://example.com/api/v1/sessions/{MASK_STRING}/validate" in masked


# =====================================================================
# Group 2: Mixed Casing & Truncated Variations
# =====================================================================

def test_adversarial_mixed_casing_secret_leak():
    """Adversarial challenge: Secret emitted with different casing in error logs or headers."""
    secret = "AdminSecretPass123"
    log_text = "Authentication failed for header X-Secret: adminsecretpass123"

    masked = mask_text(log_text, secrets=[secret])
    assert "adminsecretpass123" not in masked, f"Case-variation secret leaked: {masked}"
    assert MASK_STRING in masked


# =====================================================================
# Group 3: Playwright Trace Archive Evasion & Corrupted Archive Stress
# =====================================================================

def test_adversarial_trace_zip_uppercase_and_resource_files(tmp_path: Path):
    """Adversarial challenge: Trace archives containing uppercase extensions (TRACE.JSON)
    or Playwright network response bodies in resources/<sha1> without standard extension."""
    trace_path = tmp_path / "adversarial_trace.zip"
    secret = "ResourceSecretToken8888"

    with zipfile.ZipFile(trace_path, "w") as zf:
        # Uppercase filename
        zf.writestr("TRACE.JSON", json.dumps({"action": "fill", "secret": secret}))
        # Uppercase network
        zf.writestr("TRACE.NETWORK", f"Authorization: Bearer {secret}")
        # Playwright network resource body (hash filename, no extension)
        zf.writestr("resources/9a8b7c6d5e4f3a2b1c", json.dumps({"access_token": secret}))
        # HTML snapshot containing rendered secret
        zf.writestr("snapshot.html", f"<html><body><div id='token'>{secret}</div></body></html>")

    success = mask_playwright_trace(trace_path, secrets=[secret])
    assert success is True, "mask_playwright_trace failed to process valid zip archive"

    with zipfile.ZipFile(trace_path, "r") as zf:
        for name in ["TRACE.JSON", "TRACE.NETWORK", "resources/9a8b7c6d5e4f3a2b1c", "snapshot.html"]:
            content = zf.read(name).decode("utf-8")
            assert secret not in content, f"Secret leaked in trace archive file {name}: {content}"
            assert MASK_STRING in content, f"Mask string missing in trace archive file {name}"


def test_adversarial_trace_zip_corrupted_and_truncated(tmp_path: Path):
    """Adversarial challenge: Corrupted, empty, or truncated ZIP files submitted to mask_playwright_trace."""
    # 1. Non-existent file
    assert mask_playwright_trace(tmp_path / "non_existent.zip", secrets=["secret"]) is False

    # 2. Corrupt/garbage file
    corrupt_file = tmp_path / "corrupt.zip"
    corrupt_file.write_bytes(b"PK\x03\x04This is not a real zip file header garbage...")
    assert mask_playwright_trace(corrupt_file, secrets=["secret"]) is False

    # 3. Truncated zip file (valid header but cut off mid-stream)
    truncated_file = tmp_path / "truncated.zip"
    with zipfile.ZipFile(truncated_file, "w") as zf:
        zf.writestr("trace.trace", "some valid content")
    raw = truncated_file.read_bytes()
    truncated_file.write_bytes(raw[: len(raw) // 2])  # cut in half
    assert mask_playwright_trace(truncated_file, secrets=["secret"]) is False


def test_adversarial_trace_zip_deeply_nested_directories(tmp_path: Path):
    """Adversarial challenge: Multi-file zip archive with 30 files in deeply nested subdirectories."""
    trace_path = tmp_path / "nested_trace.zip"
    secret = "DeepNestedSecret999"

    with zipfile.ZipFile(trace_path, "w") as zf:
        for i in range(10):
            zf.writestr(f"sub_{i}/level2/trace_{i}.json", json.dumps({"run": i, "sec": secret}))
            zf.writestr(f"sub_{i}/network_{i}.network", f"Bearer {secret}")

    assert mask_playwright_trace(trace_path, secrets=[secret]) is True

    with zipfile.ZipFile(trace_path, "r") as zf:
        for item in zf.infolist():
            content = zf.read(item.filename).decode("utf-8")
            assert secret not in content, f"Secret leaked in nested file {item.filename}"


# =====================================================================
# Group 4: Auth Profile Session Injection & Malformed Variations
# =====================================================================

def test_adversarial_auth_profile_with_headers_and_direct_tokens():
    """Adversarial challenge: Auth profile containing 'headers' dictionary and direct 'token' fields."""
    secret_header_tok = "tok_custom_header_secret_777"
    secret_direct_tok = "tok_direct_secret_888"
    secret_api_key = "api_key_custom_999"

    auth_profile = {
        "headers": {
            "Authorization": f"CustomScheme {secret_header_tok}",
            "X-API-Secret": secret_api_key,
        },
        "token": secret_direct_tok,
        "sessionToken": "tok_session_111",
    }

    extracted = extract_secrets_from_auth_profile(auth_profile)
    assert secret_header_tok in extracted, f"Header token not extracted: {extracted}"
    assert secret_api_key in extracted, f"Header API key not extracted: {extracted}"
    assert secret_direct_tok in extracted, f"Direct token not extracted: {extracted}"
    assert "tok_session_111" in extracted, f"SessionToken not extracted: {extracted}"


def test_adversarial_auth_profile_dict_cookies_and_malformed_structures():
    """Adversarial challenge: Auth profile where 'cookies' is a dict or contains malformed objects."""
    secret_cookie = "cookie_secret_val_555"
    auth_profile = {
        # Dict of cookie name -> value
        "cookies": {
            "session_id": secret_cookie,
            "remember_me": "cookie_remember_val_666",
        }
    }

    extracted = extract_secrets_from_auth_profile(auth_profile)
    assert secret_cookie in extracted, f"Dict-style cookie value not extracted: {extracted}"
    assert "cookie_remember_val_666" in extracted, f"Dict-style cookie value not extracted: {extracted}"


def test_adversarial_auth_profile_json_string_masked_in_project_response():
    """Adversarial challenge: ProjectResponse masking when auth_profile_json is stored/returned as JSON string."""
    secret = "secret_stringified_token_444"
    json_str = json.dumps({"bearer_token": secret, "localStorage": {"jwt": secret}})

    response = ProjectResponse(
        id="proj_1",
        name="Adversarial Auth",
        base_url="https://example.com",
        auth_profile_json=json_str,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    data = response.model_dump()
    dumped_str = json.dumps(data["auth_profile_json"])
    assert secret not in dumped_str, f"Plaintext secret survived in stringified auth_profile_json: {dumped_str}"


def test_adversarial_project_response_masks_headers_in_auth_profile():
    """Adversarial challenge: ProjectResponse must redact credentials inside auth_profile_json['headers']."""
    secret = "secret_header_jwt_token_123"
    auth_prof = {
        "headers": {
            "Authorization": f"Bearer {secret}",
            "X-Secret-Key": secret,
        }
    }

    response = ProjectResponse(
        id="proj_2",
        name="Headers Project",
        base_url="https://example.com",
        auth_profile_json=auth_prof,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    data = response.model_dump()
    headers = data["auth_profile_json"].get("headers", {})
    assert secret not in str(headers), f"Secret leaked in ProjectResponse auth_profile headers: {headers}"


# =====================================================================
# Group 5: Test Definition Step Extraction (Edge Selectors)
# =====================================================================

def test_adversarial_test_definition_selector_variations():
    """Adversarial challenge: Test actions filling password into non-standard selectors
    (e.g. input[name='pass'], #login-pass, input#passcode, input[name='pin'])."""
    definition = {
        "steps": [
            {"action": "fill", "selector": "input[name='pass']", "value": "SecretPass1!"},
            {"action": "fill", "selector": "#login-pass", "value": "SecretPass2!"},
            {"action": "fill", "selector": "input#passcode", "value": "SecretPass3!"},
            {"action": "fill", "selector": "input[name='pin']", "value": "SecretPin4!"},
        ]
    }

    extracted = extract_secrets_from_test_definition(definition)
    for s in ["SecretPass1!", "SecretPass2!", "SecretPass3!", "SecretPin4!"]:
        assert s in extracted, f"Secret '{s}' not extracted from definition steps: {extracted}"


# =====================================================================
# Group 6: Multi-line Errors, Stringified JSON, and Deep Nesting
# =====================================================================

def test_adversarial_multiline_console_errors_and_traces():
    """Adversarial challenge: Multi-line console errors and stack traces containing secrets."""
    secret = "FatalStackSecretP@ss"
    multiline_stack = (
        "Traceback (most recent call last):\n"
        '  File "/app/auth/service.py", line 142, in authenticate\n'
        f"    raise AuthenticationError(f'Invalid credentials for password: {secret}')\n"
        f"AuthenticationError: Invalid credentials for password: {secret}\n"
    )

    masked = mask_text(multiline_stack, secrets=[secret])
    assert secret not in masked, f"Secret leaked across multiline stack trace: {masked}"
    assert MASK_STRING in masked


def test_adversarial_stringified_json_inside_logs():
    """Adversarial challenge: JSON stringified with escaped quotes inside a log string
    (e.g. '{\"password\": \"secret123\", \"token\": \"tok456\"}')."""
    secret = "EscapedSecretVal789"
    escaped_log = f'Server received payload: {{\"password\": \"{secret}\", \"user\": \"admin\"}}'

    masked = mask_text(escaped_log, secrets=[secret])
    assert secret not in masked, f"Secret leaked in escaped JSON log: {masked}"
    assert MASK_STRING in masked


def test_adversarial_deeply_nested_dictionary_structures():
    """Adversarial challenge: Nested dict/list structure 8 levels deep containing sensitive keys."""
    nested = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "level5": [
                            {"safe": "ok"},
                            {"deep_secret": "DeepValue999", "password": "ClearPassword!"},
                        ]
                    }
                }
            }
        }
    }

    masked = mask_sensitive_data(nested)
    l5 = masked["level1"]["level2"]["level3"]["level4"]["level5"][1]
    assert l5["password"] == MASK_STRING
    assert l5["deep_secret"] == MASK_STRING

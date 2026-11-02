"""Unit tests for Pillar 2: Authentication & Session Injection."""

import pytest
from unittest.mock import MagicMock
from apps.worker.runner.auth import inject_auth_profile


def test_inject_auth_profile_headers_and_cookies():
    mock_context = MagicMock()
    mock_page = MagicMock()

    auth_profile = {
        "headers": {"Authorization": "Bearer test-jwt-token", "X-Custom-Tenant": "tenant-42"},
        "cookies": [
            {"name": "session_id", "value": "xyz123", "domain": "localhost", "path": "/"},
            {"name": "remember_me", "value": "true"},
        ],
        "local_storage": [
            {"key": "user_role", "value": "super_admin"},
        ],
    }

    inject_auth_profile(
        context=mock_context,
        page=mock_page,
        base_url="http://localhost:3000",
        auth_profile=auth_profile,
    )

    # Verify extra headers called
    mock_context.set_extra_http_headers.assert_called_once_with({
        "Authorization": "Bearer test-jwt-token",
        "X-Custom-Tenant": "tenant-42",
    })

    # Verify cookies injected
    mock_context.add_cookies.assert_called_once()
    injected_cookies = mock_context.add_cookies.call_args[0][0]
    assert len(injected_cookies) == 2
    assert injected_cookies[0]["name"] == "session_id"
    assert injected_cookies[0]["value"] == "xyz123"
    assert injected_cookies[1]["domain"] == "localhost"

    # Verify localStorage init script
    mock_page.add_init_script.assert_called_once()
    script = mock_page.add_init_script.call_args[0][0]
    assert "user_role" in script
    assert "super_admin" in script


def test_inject_auth_profile_empty_or_none_safe():
    mock_context = MagicMock()
    mock_page = MagicMock()

    inject_auth_profile(context=mock_context, page=mock_page, base_url="http://localhost:3000", auth_profile=None)
    mock_context.set_extra_http_headers.assert_not_called()
    mock_context.add_cookies.assert_not_called()
    mock_page.add_init_script.assert_not_called()


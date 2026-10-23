"""Automated security tests for SSRF defense, loopback restrictions, and origin confinement."""

import pytest
from apps.worker.runner.security import (
    resolve_target_url,
    resolve_and_validate_host,
    SecurityValidationError,
)


def test_ssrf_blocks_private_networks_by_default():
    # 1. AWS/Cloud metadata IP (169.254.169.254)
    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_target_url("http://169.254.169.254/latest/meta-data/", "http://169.254.169.254", allow_local=False)

    # 2. Local loopback (127.0.0.1, localhost)
    with pytest.raises(SecurityValidationError, match="loopback"):
        resolve_target_url("http://127.0.0.1:8080/admin", "http://127.0.0.1:8080", allow_local=False)

    with pytest.raises(SecurityValidationError, match="loopback"):
        resolve_target_url("http://localhost:3000/", "http://localhost:3000", allow_local=False)

    # 3. RFC1918 Private Class A (10.0.0.1)
    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_target_url("http://10.0.0.1/internal", "http://10.0.0.1", allow_local=False)

    # 4. RFC1918 Private Class C (192.168.1.1)
    with pytest.raises(SecurityValidationError, match="blocked"):
        resolve_target_url("http://192.168.1.1/", "http://192.168.1.1", allow_local=False)


def test_origin_confinement():
    # Attempting to navigate outside project origin
    base_url = "https://example.com"
    disallowed_jump = "https://attacker.com/steal-creds"

    with pytest.raises(SecurityValidationError, match="does not match base origin"):
        resolve_target_url(disallowed_jump, base_url, allow_local=False)


def test_unsupported_protocols_blocked():
    base_url = "https://example.com"
    with pytest.raises(SecurityValidationError, match="Unsupported URL protocol"):
        resolve_target_url("file:///etc/passwd", base_url, allow_local=False)

    with pytest.raises(SecurityValidationError, match="Unsupported URL protocol"):
        resolve_target_url("gopher://127.0.0.1:70", base_url, allow_local=False)


def test_allow_local_flag_permits_fixture_testing():
    # When explicitly enabled for local dev/testing
    resolved = resolve_target_url("/search?q=test", "http://127.0.0.1:8899", allow_local=True)
    assert resolved == "http://127.0.0.1:8899/search?q=test"

"""Adversarial stress-test suite for Milestone 1: SSRF, Domain Bypass, and Path Traversal."""

import io
import socket
import tarfile
import zipfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from apps.worker.runner.security import (
    check_browser_request_security,
    is_domain_allowed,
    resolve_and_validate_host,
    SecurityValidationError,
)


# ============================================================================
# Section 1: Adversarial SSRF Probing (Configuration & Runtime)
# ============================================================================

@pytest.mark.parametrize("adversarial_url, description", [
    # IPv6 Loopback variants
    ("http://[::1]:8080", "Standard IPv6 loopback"),
    ("http://[0:0:0:0:0:0:0:1]:8080", "Uncompressed IPv6 loopback (short)"),
    ("http://[0000:0000:0000:0000:0000:0000:0000:0001]:8080", "Fully expanded IPv6 loopback"),
    ("http://[::]:8080", "Unspecified IPv6 address"),
    ("http://[0:0:0:0:0:0:0:0]:8080", "Expanded unspecified IPv6 address"),

    # IPv4-mapped IPv6 variants (RFC 4291)
    ("http://[::ffff:127.0.0.1]:8080", "IPv4-mapped IPv6 loopback dotted"),
    ("http://[::ffff:7f00:1]:8080", "IPv4-mapped IPv6 loopback hex"),
    ("http://[0:0:0:0:0:ffff:7f00:1]:8080", "Expanded IPv4-mapped IPv6 loopback"),
    ("http://[::ffff:169.254.169.254]", "IPv4-mapped cloud metadata dotted"),
    ("http://[::ffff:a9fe:a9fe]", "IPv4-mapped cloud metadata hex"),
    ("http://[::ffff:10.0.0.1]:8080", "IPv4-mapped RFC 1918 Class A"),
    ("http://[::ffff:a00:1]:8080", "IPv4-mapped RFC 1918 Class A hex"),
    ("http://[::ffff:172.16.0.1]:8080", "IPv4-mapped RFC 1918 Class B"),
    ("http://[::ffff:192.168.1.1]:8080", "IPv4-mapped RFC 1918 Class C"),

    # NAT64 translation prefix (64:ff9b::/96)
    ("http://[64:ff9b::127.0.0.1]", "NAT64 translated loopback"),
    ("http://[64:ff9b::169.254.169.254]", "NAT64 translated cloud metadata"),
    ("http://[64:ff9b::10.0.0.1]", "NAT64 translated private IP"),

    # IPv6 Special & Reserved ranges
    ("http://[fc00::1]:8080", "IPv6 Unique Local Address (ULA) fc00::/7"),
    ("http://[fd12:3456:789a::1]:8080", "IPv6 Unique Local Address (ULA) fd00::/8"),
    ("http://[fe80::1]:8080", "IPv6 Link-Local unicast fe80::/10"),
    ("http://[fe80::dead:beef]:8080", "IPv6 Link-Local unicast"),
    ("http://[2001:db8::1]:8080", "IPv6 Documentation prefix 2001:db8::/32"),
    ("http://[ff02::1]:8080", "IPv6 Multicast ff00::/8"),

    # Non-standard IP encodings & special notations
    ("http://0.0.0.0:8000", "Zero network IPv4 (current host)"),
    ("http://127.127.127.127:8000", "High-order loopback address"),
    ("http://127.0.0.2:8000", "Secondary loopback address"),
    ("http://2130706433:8000", "Decimal encoded loopback 127.0.0.1"),
    ("http://2852039166", "Decimal encoded cloud metadata 169.254.169.254"),
    ("http://167772161", "Decimal encoded RFC 1918 10.0.0.1"),
    ("http://0x7f000001:8000", "Hexadecimal encoded loopback 127.0.0.1"),
    ("http://0xa9fea9fe", "Hexadecimal encoded cloud metadata 169.254.169.254"),
    ("http://017700000001:8000", "Octal encoded loopback 127.0.0.1"),

    # Userinfo & credential confusion SSRF
    ("http://user:pass@127.0.0.1:8080/", "Credentials with loopback destination"),
    ("http://admin:secret@169.254.169.254/latest/meta-data/", "Credentials with metadata destination"),
    ("http://example.com@127.0.0.1/", "Origin confusion with loopback destination"),
    ("http://example.com@[::1]/", "Origin confusion with IPv6 loopback destination"),
    ("http://user@10.0.0.1:8080/", "Credentials with private IP destination"),

    # High / unusual port boundaries
    ("http://127.0.0.1:65535", "Loopback maximum port"),
    ("http://169.254.169.254:80", "Metadata default port"),
    ("http://10.255.255.254:443", "RFC 1918 boundary IP"),
])
def test_create_project_rejects_adversarial_ssrf_urls(client: TestClient, monkeypatch, adversarial_url: str, description: str):
    """Adversarial stress test: all non-routable, loopback, private, and metadata URLs must be rejected."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_TARGETS", False)
    payload = {
        "name": f"Adversarial Target: {description}",
        "base_url": adversarial_url,
        "allow_local_loopback": False,
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code in [400, 422], f"Expected 400/422 for {adversarial_url} ({description}), got {response.status_code}: {response.text}"
    detail = response.json().get("detail", "")
    if isinstance(detail, list):
        detail = str(detail)
    detail = detail.lower()
    assert any(term in detail for term in ["ssrf", "blocked", "loopback", "could not resolve", "invalid", "null"]), (
        f"Expected security block reason in detail for {adversarial_url}, got: {detail}"
    )


# ============================================================================
# Section 2: Mode A Development Controls vs Strict Production Guard
# ============================================================================

def test_mode_a_allows_loopback_in_dev_but_strictly_blocks_rfc1918_and_metadata(client: TestClient, monkeypatch):
    """In dev mode with allow_local_loopback=True, only 127.0.0.1/localhost/::1 are allowed, not private CIDRs."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Allowed loopback in dev mode
    allowed_dev_urls = ["http://127.0.0.1:3000", "http://localhost:8080", "http://[::1]:9000"]
    for url in allowed_dev_urls:
        res = client.post("/api/v1/projects", json={
            "name": "Valid Dev Project",
            "base_url": url,
            "allow_local_loopback": True,
        })
        assert res.status_code == 201, f"Expected 201 for {url} in dev mode, got {res.status_code}: {res.text}"

    # NEVER allowed even with allow_local_loopback=True
    forbidden_urls = [
        "http://10.0.0.1:8080",
        "http://172.16.0.1:3000",
        "http://192.168.1.1:80",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::ffff:169.254.169.254]",
        "http://[fc00::1]:8080",
    ]
    for url in forbidden_urls:
        res = client.post("/api/v1/projects", json={
            "name": "Bypass Attempt",
            "base_url": url,
            "allow_local_loopback": True,
        })
        assert res.status_code == 400, f"Expected 400 for {url} even with allow_local_loopback=True, got {res.status_code}"
        assert "blocked" in res.json().get("detail", "").lower()


def test_production_mode_strictly_forbids_loopback_regardless_of_flag(client: TestClient, monkeypatch):
    """When ENVIRONMENT=production, loopback is strictly prohibited even if allow_local_loopback=True."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    for url in ["http://localhost:3000", "http://127.0.0.1:8000", "http://[::1]:8080"]:
        res = client.post("/api/v1/projects", json={
            "name": "Prod Loopback Attack",
            "base_url": url,
            "allow_local_loopback": True,
        })
        assert res.status_code == 400, f"Expected 400 for {url} in production mode, got {res.status_code}"
        detail = res.json().get("detail", "").lower()
        assert "loopback" in detail or "blocked" in detail


# ============================================================================
# Section 3: DNS Multi-Homed & Rebinding Edge Cases
# ============================================================================

def test_dns_resolution_blocks_if_any_ip_is_private(client: TestClient):
    """Multi-homed DNS lookup returning a public IP followed by a private IP must be rejected."""
    multi_homed_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),      # Public
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80)),    # Cloud metadata
    ]
    with patch("socket.getaddrinfo", return_value=multi_homed_info):
        res = client.post("/api/v1/projects", json={
            "name": "Multi-Homed DNS Attack",
            "base_url": "https://attacker-controlled.com",
        })
        assert res.status_code == 400
        assert "resolved to blocked private destination" in res.json().get("detail", "")


def test_dns_resolution_blocks_if_ipv6_is_ula(client: TestClient):
    """DNS lookup returning an IPv6 ULA address (fc00::/7) must be rejected."""
    ula_info = [
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::dead:beef", 80, 0, 0)),
    ]
    with patch("socket.getaddrinfo", return_value=ula_info):
        res = client.post("/api/v1/projects", json={
            "name": "IPv6 ULA DNS Target",
            "base_url": "https://internal-ipv6.corp",
        })
        assert res.status_code == 400
        assert "resolved to blocked private destination" in res.json().get("detail", "")


# ============================================================================
# Section 4: Domain Allowlist Adversarial Suffix & Wildcard Exploits
# ============================================================================

def test_domain_allowlist_adversarial_wildcard_escapes():
    """Stress tests wildcard subdomain matching against prefix/suffix spoofing."""
    base_url = "https://legit.example.com"
    allowed_domains = ["*.example.com", "partner.io", "127.0.0.1:8080"]

    # Legitimate matching
    assert is_domain_allowed("api.example.com", base_url, allowed_domains) is True
    assert is_domain_allowed("sub.api.example.com", base_url, allowed_domains) is True
    assert is_domain_allowed("example.com", base_url, allowed_domains) is True
    assert is_domain_allowed("partner.io", base_url, allowed_domains) is True
    assert is_domain_allowed("127.0.0.1:8080", base_url, allowed_domains) is True

    # Adversarial attacks that MUST be rejected:
    # 1. Attacker registered suffix domain
    assert is_domain_allowed("example.com.attacker.com", base_url, allowed_domains) is False
    assert is_domain_allowed("api.example.com.attacker.org", base_url, allowed_domains) is False

    # 2. Hyphenated domain spoofing
    assert is_domain_allowed("evil-example.com", base_url, allowed_domains) is False
    assert is_domain_allowed("example-com.net", base_url, allowed_domains) is False

    # 3. Suffix overlap without dot separator
    assert is_domain_allowed("notexample.com", base_url, allowed_domains) is False
    assert is_domain_allowed("myexample.com", base_url, allowed_domains) is False

    # 4. Port mismatch on port-specific entry
    assert is_domain_allowed("127.0.0.1:3000", base_url, allowed_domains) is False
    assert is_domain_allowed("127.0.0.1:9000", base_url, allowed_domains) is False
    assert is_domain_allowed("127.0.0.1", base_url, allowed_domains) is False

    # 5. Completely unlisted domains
    assert is_domain_allowed("google.com", base_url, allowed_domains) is False
    assert is_domain_allowed("sub.partner.io", base_url, allowed_domains) is False  # partner.io was not wildcard


def test_userinfo_navigation_spoofing_rejected():
    """Navigation to http://legit.example.com@attacker.com must NOT match legit.example.com."""
    base_url = "https://legit.example.com"
    allowed_domains = ["legit.example.com"]

    # Browser navigates to attacker.com with username legit.example.com
    spoofed_nav_url = "https://legit.example.com@attacker.com/steal"
    ok, reason = check_browser_request_security(
        url=spoofed_nav_url,
        base_url=base_url,
        allowed_domains=allowed_domains,
        is_navigation=True,
    )
    assert ok is False, "Userinfo domain spoofing was unexpectedly allowed!"
    assert "out-of-bounds" in reason or "not authorized" in reason


# ============================================================================
# Section 5: Zip Slip & Tar Slip Path Traversal Exploits
# ============================================================================

def test_source_upload_rejects_adversarial_zip_slip_payloads(client: TestClient):
    """Uploads zip archives containing various path traversal techniques; all must be rejected."""
    # Create project
    proj_res = client.post("/api/v1/projects", json={
        "name": "Zip Slip Stress Test",
        "base_url": "https://example.com",
    })
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    zip_traversal_payloads = [
        ("../../etc/passwd", "Unix relative traversal"),
        ("..\\..\\Windows\\System32\\calc.exe", "Windows backslash relative traversal"),
        ("/tmp/evil.sh", "Unix absolute root path"),
        ("C:\\Windows\\system.ini", "Windows absolute drive letter path"),
        ("C:/Windows/system.ini", "Windows drive letter forward slash"),
        ("\\Windows\\system.ini", "Windows root-relative path"),
        ("sub/folder/../../../../evil.txt", "Deep nested relative traversal"),
        ("safe_dir/../../../evil.txt", "Prefix directory traversal"),
    ]

    for malicious_filename, label in zip_traversal_payloads:
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr(malicious_filename, "echo pwned")
        bio.seek(0)

        res = client.post(
            f"/api/v1/projects/{proj_id}/source-upload",
            files={"file": ("exploit.zip", bio, "application/zip")},
        )
        assert res.status_code == 400, f"Expected 400 for Zip Slip payload '{malicious_filename}' ({label}), got {res.status_code}"
        assert "path traversal detected" in res.json().get("detail", "").lower()


def test_source_upload_rejects_adversarial_tar_slip_and_symlink_payloads(client: TestClient):
    """Uploads tar archives containing directory traversal and malicious symlinks."""
    proj_res = client.post("/api/v1/projects", json={
        "name": "Tar Slip Stress Test",
        "base_url": "https://example.com",
    })
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # 1. Tar relative path traversal member
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        data = b"malicious content"
        ti = tarfile.TarInfo(name="../../etc/shadow")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    bio.seek(0)
    res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("exploit.tar.gz", bio, "application/gzip")},
    )
    assert res.status_code == 400
    assert "path traversal detected" in res.json().get("detail", "").lower()

    # 2. Tar symlink pointing outside destination directory (relative escape)
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        ti = tarfile.TarInfo(name="symlink_escape")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "../../etc/passwd"
        tf.addfile(ti)
    bio.seek(0)
    res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("symlink_escape.tar.gz", bio, "application/gzip")},
    )
    assert res.status_code == 400
    assert "symlink traversal detected" in res.json().get("detail", "").lower()

    # 3. Tar symlink pointing to absolute Unix root
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        ti = tarfile.TarInfo(name="symlink_abs_root")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/etc/passwd"
        tf.addfile(ti)
    bio.seek(0)
    res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("symlink_abs.tar.gz", bio, "application/gzip")},
    )
    assert res.status_code == 400
    assert "symlink traversal detected" in res.json().get("detail", "").lower()

    # 4. Tar symlink pointing to Windows system file
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        ti = tarfile.TarInfo(name="symlink_win")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "C:\\Windows\\system.ini"
        tf.addfile(ti)
    bio.seek(0)
    res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("symlink_win.tar.gz", bio, "application/gzip")},
    )
    assert res.status_code == 400
    assert "symlink traversal detected" in res.json().get("detail", "").lower()


def test_source_directory_rejects_null_byte_and_nonexistent_paths(client: TestClient, tmp_path):
    """POST /projects/{id}/source-directory must reject null bytes and non-existent paths."""
    proj_res = client.post("/api/v1/projects", json={
        "name": "Local Directory Security Test",
        "base_url": "https://example.com",
    })
    proj_id = proj_res.json()["id"]

    # 1. Null byte injection
    res_null = client.post(f"/api/v1/projects/{proj_id}/source-directory", json={
        "source_directory": f"{tmp_path}\x00/secret",
    })
    assert res_null.status_code in [400, 422]
    detail = str(res_null.json().get("detail", "")).lower()
    assert any(w in detail for w in ["null byte", "null", "invalid"])

    # 2. Non-existent path
    res_missing = client.post(f"/api/v1/projects/{proj_id}/source-directory", json={
        "source_directory": str(tmp_path / "definitely_non_existent_folder_12345"),
    })
    assert res_missing.status_code == 400
    assert "does not exist" in res_missing.json().get("detail", "").lower()

    # 3. Path pointing to a file instead of a directory
    test_file = tmp_path / "regular_file.txt"
    test_file.write_text("just a file")
    res_file = client.post(f"/api/v1/projects/{proj_id}/source-directory", json={
        "source_directory": str(test_file),
    })
    assert res_file.status_code == 400
    assert "not a directory" in res_file.json().get("detail", "").lower()

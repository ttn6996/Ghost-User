"""Automated tests for configuration-time project security, SSRF validation, and Mode A controls."""

import io
import socket
import zipfile
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings


# 1. Comprehensive CIDR Rejection Matrix
@pytest.mark.parametrize("blocked_url, expected_match", [
    ("http://10.0.0.1/admin", "blocked private or reserved network"),
    ("http://10.254.254.1:8080", "blocked private or reserved network"),
    ("http://172.16.0.1/", "blocked private or reserved network"),
    ("http://172.31.255.254/api", "blocked private or reserved network"),
    ("http://192.168.0.1/", "blocked private or reserved network"),
    ("http://192.168.1.100:3000", "blocked private or reserved network"),
    ("http://169.254.169.254/latest/meta-data/", "blocked private or reserved network"),
    ("http://169.254.1.1", "blocked private or reserved network"),
    ("http://0.0.0.0:80", "blocked private or reserved network"),
    ("http://100.64.0.1:8080", "blocked private or reserved network"),
    ("http://192.0.2.1", "blocked private or reserved network"),
    ("http://198.51.100.1", "blocked private or reserved network"),
    ("http://203.0.113.1", "blocked private or reserved network"),
    ("http://224.0.0.1", "blocked private or reserved network"),
    ("http://255.255.255.255", "blocked private or reserved network"),
    ("http://[::ffff:169.254.169.254]", "blocked private or reserved network"),
    ("http://[::ffff:10.0.0.1]", "blocked private or reserved network"),
    ("http://[fd00::1]", "blocked private or reserved network"),
    ("http://[fe80::1]", "blocked private or reserved network"),
])
def test_create_project_rejects_blocked_cidrs(client: TestClient, blocked_url: str, expected_match: str):
    """Verifies that POST /api/v1/projects rejects all blocked private and cloud metadata CIDRs."""
    payload = {
        "name": "Malicious CIDR Target",
        "base_url": blocked_url,
        "description": "Attempting SSRF via private CIDR",
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "SSRF validation" in detail or expected_match in detail or "blocked" in detail.lower()


# 2. Loopback Handling: Default Rejection vs. Mode A Dev Bypass
def test_create_project_rejects_loopback_by_default(client: TestClient, monkeypatch):
    """Loopback addresses must be rejected when allow_local_loopback is False."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_TARGETS", False)
    for loopback_url in ["http://127.0.0.1:8000", "http://localhost:3000", "http://[::1]:8080"]:
        response = client.post("/api/v1/projects", json={
            "name": "Local Loopback Project",
            "base_url": loopback_url,
            "allow_local_loopback": False,
        })
        assert response.status_code == 400
        assert "loopback" in response.json()["detail"].lower()


def test_create_project_permits_mode_a_local_loopback_in_dev_mode(client: TestClient, monkeypatch):
    """Mode A: In non-production, setting allow_local_loopback=True permits localhost."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    for loopback_url in ["http://127.0.0.1:3000", "http://localhost:8080"]:
        response = client.post("/api/v1/projects", json={
            "name": "Local Dev Audit Project",
            "base_url": loopback_url,
            "allow_local_loopback": True,
            "execution_mode": "mode_a_manual",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["base_url"] == loopback_url
        assert data["allow_local_loopback"] is True


def test_mode_a_local_loopback_never_permits_rfc1918_private_cidrs(client: TestClient, monkeypatch):
    """allow_local_loopback must ONLY permit 127.0.0.1/localhost, NEVER 10.0.0.0/8 or 169.254.169.254."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    response = client.post("/api/v1/projects", json={
        "name": "Bypass Attempt",
        "base_url": "http://10.0.0.1:8080",
        "allow_local_loopback": True,
    })
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


def test_create_project_production_mode_overrides_allow_local(client: TestClient, monkeypatch):
    """In production mode, loopback is strictly rejected even if allow_local_loopback=True."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = client.post("/api/v1/projects", json={
        "name": "Prod Leak Attempt",
        "base_url": "http://127.0.0.1:8000",
        "allow_local_loopback": True,
    })
    assert response.status_code == 400
    assert "loopback" in response.json()["detail"].lower() or "production" in response.json()["detail"].lower()


# 3. DNS Pre-Resolution Rejection
def test_create_project_dns_resolution_private_ip(client: TestClient):
    """Hostnames that resolve to private/loopback IPs must be blocked during project creation."""
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.50.1.20", 80))]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        response = client.post("/api/v1/projects", json={
            "name": "DNS Rebind Target",
            "base_url": "https://internal-portal.corp.net",
        })
        assert response.status_code == 400
        assert "resolved to blocked private destination" in response.json()["detail"]


def test_create_project_dns_multi_homed_partial_private_ip(client: TestClient, monkeypatch):
    """If any IP returned by DNS is in a blocked network, project creation must fail."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_TARGETS", False)
    dual_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)), # public
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),     # loopback
    ]
    with patch("socket.getaddrinfo", return_value=dual_addrinfo):
        response = client.post("/api/v1/projects", json={
            "name": "Dual Homed DNS",
            "base_url": "https://dual-homed.example.com",
            "allow_local_loopback": False,
        })
        assert response.status_code == 400
        assert "resolved to blocked" in response.json()["detail"] or "loopback" in response.json()["detail"]


def test_create_project_unresolvable_hostname_rejected(client: TestClient):
    """Unresolvable hostnames must return HTTP 400 Bad Request."""
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        response = client.post("/api/v1/projects", json={
            "name": "Dead Domain Project",
            "base_url": "https://this-domain-does-not-exist-at-all-999.test",
        })
        assert response.status_code == 400
        assert "could not resolve" in response.json()["detail"].lower()


# 4. Protocol & Scheme Enforcement
@pytest.mark.parametrize("invalid_scheme_url", [
    "file:///etc/passwd",
    "file:///C:/Windows/system.ini",
    "gopher://127.0.0.1:70",
    "ftp://ftp.example.com/file.zip",
    "javascript:alert(1)",
    "data:text/html,<html>Hello</html>",
])
def test_create_project_rejects_non_http_schemes(client: TestClient, invalid_scheme_url: str):
    """Only http and https protocols are permitted."""
    response = client.post("/api/v1/projects", json={
        "name": "Protocol Exploit",
        "base_url": invalid_scheme_url,
    })
    assert response.status_code in [400, 422]


# 5. Project Update SSRF Validation (PUT /api/v1/projects/{id})
def test_update_project_rejects_blocked_base_url(client: TestClient):
    """PUT /api/v1/projects/{id} must validate base_url updates against SSRF rules."""
    create_res = client.post("/api/v1/projects", json={
        "name": "Valid Project",
        "base_url": "https://example.com",
    })
    assert create_res.status_code == 201
    proj_id = create_res.json()["id"]

    # Attempt to update base_url to cloud metadata IP
    update_res = client.put(f"/api/v1/projects/{proj_id}", json={
        "base_url": "http://169.254.169.254/latest/meta-data/",
    })
    assert update_res.status_code == 400
    assert "blocked" in update_res.json()["detail"].lower()

    # Verify project was not modified
    get_res = client.get(f"/api/v1/projects/{proj_id}")
    assert get_res.json()["base_url"] == "https://example.com"


# 6. Local Source Path Validation (Pillar 1)
def test_create_project_validates_source_code_path(client: TestClient, tmp_path):
    """Validates that configured source_code_path must exist on disk."""
    fake_path = str(tmp_path / "non_existent_project_dir_xyz")
    res_bad = client.post("/api/v1/projects", json={
        "name": "Local Audit Bad Path",
        "base_url": "https://example.com",
        "source_code_path": fake_path,
    })
    assert res_bad.status_code == 400
    assert "source_code_path does not exist" in res_bad.json()["detail"].lower()

    real_path = tmp_path / "my_project"
    real_path.mkdir()
    res_good = client.post("/api/v1/projects", json={
        "name": "Local Audit Good Path",
        "base_url": "https://example.com",
        "source_code_path": str(real_path),
    })
    assert res_good.status_code == 201
    assert res_good.json()["source_code_path"] == str(real_path)


# 7. Allowed Domains Validation at Creation Time
def test_create_project_validates_allowed_domains_ssrf(client: TestClient):
    """Allowed domains list must not contain private/cloud metadata IPs."""
    res = client.post("/api/v1/projects", json={
        "name": "Allowlist SSRF Project",
        "base_url": "https://example.com",
        "allowed_domains": ["api.example.com", "169.254.169.254"],
    })
    assert res.status_code == 400
    assert "blocked" in res.json()["detail"].lower()


# 8. Source Directory Linking & Upload Endpoints
def test_project_source_directory_linking(client: TestClient, tmp_path):
    """Link an existing local directory to project workspace."""
    source_dir = tmp_path / "CampusHub-Frontend"
    source_dir.mkdir()
    (source_dir / "package.json").write_text('{"name": "campushub"}')

    proj_res = client.post("/api/v1/projects", json={
        "name": "CampusHub Project",
        "base_url": "https://example.com",
    })
    proj_id = proj_res.json()["id"]

    link_res = client.post(f"/api/v1/projects/{proj_id}/source-directory", json={
        "source_directory": str(source_dir),
    })
    assert link_res.status_code == 200
    assert link_res.json()["extracted_files_count"] == 1

    # Verify source info endpoint
    info_res = client.get(f"/api/v1/projects/{proj_id}/source")
    assert info_res.status_code == 200
    assert info_res.json()["has_source_code"] is True
    assert info_res.json()["files_count"] == 1


def test_project_source_upload_zip_slip_rejected(client: TestClient):
    """Uploading zip archive containing path traversal (Zip Slip) must be rejected with 400."""
    proj_res = client.post("/api/v1/projects", json={
        "name": "Zip Slip Guard",
        "base_url": "https://example.com",
    })
    proj_id = proj_res.json()["id"]

    # Build malicious zip in-memory with traversal path
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:::")
    bio.seek(0)

    upload_res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("malicious.zip", bio, "application/zip")},
    )
    assert upload_res.status_code == 400
    assert "Path traversal detected" in upload_res.json()["detail"]


def test_project_source_upload_valid_zip(client: TestClient):
    """Uploading valid zip extracts files and updates project workspace."""
    proj_res = client.post("/api/v1/projects", json={
        "name": "Valid Upload Project",
        "base_url": "https://example.com",
    })
    proj_id = proj_res.json()["id"]

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("src/index.js", "console.log('hello');")
        zf.writestr("package.json", '{"name": "test"}')
    bio.seek(0)

    upload_res = client.post(
        f"/api/v1/projects/{proj_id}/source-upload",
        files={"file": ("source.zip", bio, "application/zip")},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["extracted_files_count"] == 2

    info_res = client.get(f"/api/v1/projects/{proj_id}/source")
    assert info_res.status_code == 200
    assert info_res.json()["has_source_code"] is True
    assert info_res.json()["files_count"] == 2

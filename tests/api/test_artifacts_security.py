"""Tests for artifact authorization boundaries and path traversal protection."""

import os
from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import settings


def test_path_traversal_blocked(client: TestClient, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    # 1. Direct traversal in test_run_id
    res = client.get("/api/v1/artifacts/../../etc/passwd")
    assert res.status_code in (400, 404)

    # 2. Direct traversal in file_path
    res = client.get("/api/v1/artifacts/valid-run-id/../../../windows/win.ini")
    assert res.status_code in (400, 404)

    # 3. Encoded null byte and dot-dot traversal
    res = client.get("/api/v1/artifacts/valid-run-id/file%00.png")
    assert res.status_code in (400, 404)

    res = client.get("/api/v1/artifacts/valid-run-id/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert res.status_code in (400, 404)


def test_symlink_artifact_rejected(client: TestClient, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    run_dir = tmp_path / "symlink-run-id"
    run_dir.mkdir(parents=True, exist_ok=True)
    real_file = run_dir / "real.png"
    real_file.write_bytes(b"image_content")

    # Create symlink pointing to the file
    symlink_file = run_dir / "symlink.png"
    try:
        symlink_file.symlink_to(real_file)
    except (OSError, NotImplementedError):
        # On Windows without developer mode/admin rights, symlinks may not be allowed
        return

    res = client.get("/api/v1/artifacts/symlink-run-id/symlink.png")
    assert res.status_code == 400
    assert "Symlinks not permitted" in res.json().get("detail", "")


def test_production_mode_authorization_boundary(client: TestClient, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    # Create dummy artifact
    run_dir = tmp_path / "auth-run-id"
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshot = run_dir / "step_0.png"
    screenshot.write_bytes(b"dummy_png_bytes")

    orig_env = settings.ENVIRONMENT
    try:
        # Switch to production environment
        settings.ENVIRONMENT = "production"

        # 1. No token configured on server -> 403 Forbidden
        if "GHOST_USER_ARTIFACT_TOKEN" in os.environ:
            del os.environ["GHOST_USER_ARTIFACT_TOKEN"]

        res = client.get("/api/v1/artifacts/auth-run-id/step_0.png")
        assert res.status_code == 403

        # 2. Token configured on server, but request has no token -> 401 Unauthorized
        os.environ["GHOST_USER_ARTIFACT_TOKEN"] = "secret-token-12345"
        res = client.get("/api/v1/artifacts/auth-run-id/step_0.png")
        assert res.status_code == 401

        # 3. Request with wrong token -> 401 Unauthorized
        res = client.get(
            "/api/v1/artifacts/auth-run-id/step_0.png",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert res.status_code == 401

        # 4. Request with valid token -> 200 OK
        res = client.get(
            "/api/v1/artifacts/auth-run-id/step_0.png",
            headers={"Authorization": "Bearer secret-token-12345"},
        )
        assert res.status_code == 200
        assert res.content == b"dummy_png_bytes"

    finally:
        settings.ENVIRONMENT = orig_env
        if "GHOST_USER_ARTIFACT_TOKEN" in os.environ:
            del os.environ["GHOST_USER_ARTIFACT_TOKEN"]

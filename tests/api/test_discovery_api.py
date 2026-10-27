"""Tests for project auto-discovery and crawl API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, DiscoveryReport
from tests.fixtures.server import start_fixture_server_in_background


def test_discover_project_endpoints(client: TestClient, db_session: Session):
    """Verifies triggering auto-discovery via API, fetching latest report, and saving a suggested test."""
    server = start_fixture_server_in_background(port=0)
    actual_port = server.server_port
    base_url = f"http://127.0.0.1:{actual_port}"

    try:
        project = Project(name="Discovery Project", base_url=base_url)
        db_session.add(project)
        db_session.commit()

        # 1. Trigger discovery
        res = client.post(f"/api/v1/projects/{project.id}/discover?max_pages=5")
        assert res.status_code == 200
        data = res.json()
        assert data["project_id"] == project.id
        assert data["status"] == "completed"
        assert data["pages_count"] >= 2
        assert len(data["suggested_tests_json"]) >= 1

        # 2. Get latest report
        res_latest = client.get(f"/api/v1/projects/{project.id}/discover/latest")
        assert res_latest.status_code == 200
        latest_data = res_latest.json()
        assert latest_data["id"] == data["id"]
        assert latest_data["pages_count"] == data["pages_count"]

        # 3. Save a suggested test into project
        suggested = data["suggested_tests_json"][0]
        res_save = client.post(
            f"/api/v1/projects/{project.id}/discover/save-test",
            json={
                "name": suggested["name"],
                "description": suggested.get("description"),
                "steps": suggested["steps"],
            },
        )
        assert res_save.status_code == 201
        created_test = res_save.json()
        assert created_test["name"] == suggested["name"]
        assert created_test["project_id"] == project.id

        # Verify test exists in DB
        db_test = db_session.get(TestCase, created_test["id"])
        assert db_test is not None
        assert db_test.definition_json["steps"] == suggested["steps"]

    finally:
        server.shutdown()
        server.server_close()


def test_discover_non_existent_project_returns_404(client: TestClient):
    """Returns 404 when project does not exist."""
    res = client.post("/api/v1/projects/non-existent-uuid/discover")
    assert res.status_code == 404

"""Integration tests for Autonomous UI Audit endpoint and service."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun, DiscoveryReport
from app.services.dev_server import DevServerInfo
from packages.shared.constants import RunStatus


def test_autonomous_audit_project_not_found(client: TestClient):
    response = client.post("/api/v1/projects/non-existent-id/autonomous-audit", json={})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_autonomous_audit_mocked_execution(client: TestClient, db_session: Session, tmp_path):
    # Setup test project
    source_dir = tmp_path / "mock_app"
    source_dir.mkdir()
    (source_dir / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")

    project = Project(
        name="Test Audit Project",
        base_url="http://127.0.0.1:3000",
        source_code_path=str(source_dir),
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    mock_crawl_result = {
        "base_url": "http://127.0.0.1:3000",
        "pages_count": 2,
        "broken_links_count": 0,
        "forms_count": 1,
        "pages": [
            {"url": "http://127.0.0.1:3000/", "path": "/", "title": "Home", "status_code": 200, "forms_count": 0, "links_found": 1, "is_broken": False},
            {"url": "http://127.0.0.1:3000/login", "path": "/login", "title": "Login", "status_code": 200, "forms_count": 1, "links_found": 0, "is_broken": False},
        ],
        "broken_links": [],
        "forms": [{"page_path": "/login", "page_url": "http://127.0.0.1:3000/login", "form_type": "Login Form", "inputs": [], "buttons": []}],
        "console_errors": [],
        "suggested_tests": [
            {
                "name": "Auto-Discovery: Sitemap Smoke Test",
                "description": "Verifies public pages",
                "steps": [{"action": "goto", "url": "/"}, {"action": "assert_visible", "selector": "body"}],
            }
        ],
    }

    mock_server_info = DevServerInfo(
        project_id=project.id,
        local_path=str(source_dir),
        command="npm run dev",
        target_url="http://127.0.0.1:3000",
        port=3000,
        is_running=True,
    )

    with patch("apps.worker.runner.crawler.WebCrawler.crawl", return_value=mock_crawl_result), \
         patch("apps.worker.runner.engine.BrowserExecutionEngine.execute_run", return_value=RunStatus.PASSED), \
         patch("app.services.dev_server.DevServerRunner.get_status", return_value=mock_server_info):

        response = client.post(
            f"/api/v1/projects/{project.id}/autonomous-audit",
            json={"auto_start_server": True, "max_pages": 5, "run_form_tests": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project.id
        assert data["status"] == "completed"
        assert data["pages_audited_count"] == 2
        assert data["broken_links_count"] == 0
        assert data["tests_executed_count"] == 1
        assert data["tests_passed_count"] == 1
        assert len(data["test_runs"]) == 1
        assert data["discovery_report_id"] is not None
        assert "Autonomous audit finished" in data["audit_summary"]

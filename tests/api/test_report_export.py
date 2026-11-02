"""Tests for standalone HTML audit report exporter."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.models import Project, DiscoveryReport


def test_export_report_project_not_found(client: TestClient):
    resp = client.get("/api/v1/projects/non-existent-id/export-report")
    assert resp.status_code == 404


def test_export_report_successful_html(client: TestClient, db_session: Session):
    project = Project(
        name="Captive Portal Production",
        base_url="http://127.0.0.1:5173",
        source_code_path="D:/Download/AMZ/Wi-Fi-Captive-Portal/wifi-captive-frontend",
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    discovery = DiscoveryReport(
        project_id=project.id,
        status="completed",
        base_url=project.base_url,
        pages_count=5,
        broken_links_count=0,
        forms_count=2,
        pages_json=[
            {"path": "/portal", "title": "Captive Portal", "status_code": 200, "forms_count": 1, "links_found": 3},
            {"path": "/admin/login", "title": "Admin Login", "status_code": 200, "forms_count": 1, "links_found": 0},
        ],
    )
    db_session.add(discovery)
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project.id}/export-report")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html_text = resp.text
    assert "Ghost-User Audit Report" in html_text
    assert "Captive Portal Production" in html_text
    assert "http://127.0.0.1:5173" in html_text
    assert "/admin/login" in html_text
    assert "Print / Save as PDF" in html_text


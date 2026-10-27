"""Tests for AI Prompt-to-Journey Generation endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project
from packages.shared.schemas import TestDefinition


def test_generate_journey_requires_existing_project(client: TestClient):
    """Returns 404 if project_id does not exist."""
    res = client.post(
        "/api/v1/test-cases/generate",
        json={"project_id": "non-existent-uuid", "prompt": "Login with user01 and admin123"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_generate_journey_vietnamese_login(client: TestClient, db_session: Session):
    """Generates valid login test steps from Vietnamese prompt."""
    project = Project(name="CampusHub", base_url="http://localhost:5173")
    db_session.add(project)
    db_session.commit()

    prompt = "Vào trang login, đăng nhập bằng tài khoản user01 và mật khẩu admin123, sau đó kiểm tra xem đã vào được trang chủ chưa"
    res = client.post(
        "/api/v1/test-cases/generate",
        json={"project_id": project.id, "prompt": prompt},
    )
    assert res.status_code == 200
    data = res.json()

    assert "Authentication Journey" in data["suggested_name"]
    assert len(data["steps"]) >= 4

    # Verify actions
    actions = [s["action"] for s in data["steps"]]
    assert "goto" in actions
    assert "fill" in actions
    assert "click" in actions

    # Verify step values
    fill_steps = [s for s in data["steps"] if s["action"] == "fill"]
    assert any(s["value"] == "user01" for s in fill_steps)
    assert any(s["value"] == "admin123" for s in fill_steps)

    # Validate against strict TestDefinition schema
    test_def = {
        "name": data["suggested_name"],
        "description": data["suggested_description"],
        "steps": data["steps"],
    }
    validated = TestDefinition.model_validate(test_def)
    assert len(validated.steps) == len(data["steps"])


def test_generate_journey_search(client: TestClient, db_session: Session):
    """Generates valid search test steps from Vietnamese search prompt."""
    project = Project(name="Shop Project", base_url="https://example.com")
    db_session.add(project)
    db_session.commit()

    prompt = "Tìm kiếm sản phẩm giáo trình trên chợ sinh viên"
    res = client.post(
        "/api/v1/test-cases/generate",
        json={"project_id": project.id, "prompt": prompt},
    )
    assert res.status_code == 200
    data = res.json()

    assert "Search" in data["suggested_name"]
    actions = [s["action"] for s in data["steps"]]
    assert "goto" in actions
    assert "fill" in actions
    assert "click" in actions

    fill_step = next(s for s in data["steps"] if s["action"] == "fill")
    assert fill_step["value"] == "giáo trình"


def test_generate_journey_negative_login(client: TestClient, db_session: Session):
    """Generates negative test with error assertion when prompt indicates incorrect credentials."""
    project = Project(name="CampusHub", base_url="http://localhost:5173")
    db_session.add(project)
    db_session.commit()

    prompt = "Đăng nhập với user01 và mật khẩu sai abc để kiểm tra thông báo lỗi"
    res = client.post(
        "/api/v1/test-cases/generate",
        json={"project_id": project.id, "prompt": prompt},
    )
    assert res.status_code == 200
    data = res.json()

    assert "Negative Test" in data["suggested_name"]
    actions = [s["action"] for s in data["steps"]]
    assert "assert_visible" in actions
    # Check that error selector is present
    assert_step = next(s for s in data["steps"] if s["action"] == "assert_visible")
    assert "bg-red" in assert_step["selector"] or "alert" in assert_step["selector"]

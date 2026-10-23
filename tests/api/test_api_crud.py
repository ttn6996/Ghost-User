"""Automated API endpoint tests."""

import pytest
from packages.shared.constants import RunStatus


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ghost-user-api"

    response_v1 = client.get("/api/v1/health")
    assert response_v1.status_code == 200


def test_project_crud(client):
    # 1. Create project
    create_payload = {
        "name": "E-Commerce QA",
        "base_url": "https://example.com",
        "description": "Production checkout journey testing",
    }
    res = client.post("/api/v1/projects", json=create_payload)
    assert res.status_code == 201
    project = res.json()
    project_id = project["id"]
    assert project["name"] == "E-Commerce QA"
    assert project["base_url"] == "https://example.com"

    # 2. List projects
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == project_id

    # 3. Get single project
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "E-Commerce QA"

    # 4. Update project
    res = client.put(f"/api/v1/projects/{project_id}", json={"name": "Updated QA Project"})
    assert res.status_code == 200
    assert res.json()["name"] == "Updated QA Project"

    # 5. Delete project
    res = client.delete(f"/api/v1/projects/{project_id}")
    assert res.status_code == 204

    # Verify not found after delete
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 404


def test_test_definition_validation(client):
    # Valid definition
    valid_def = {
        "definition_json": {
            "name": "Login flow",
            "steps": [
                {"action": "goto", "url": "/login"},
                {"action": "fill", "selector": "input#email", "value": "test@example.com"},
                {"action": "click", "selector": "button#submit"},
                {"action": "assert_visible", "selector": ".dashboard"},
            ],
        }
    }
    res = client.post("/api/v1/test-cases/validate", json=valid_def)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["step_count"] == 4
    assert len(data["errors"]) == 0

    # Invalid action type
    invalid_def = {
        "definition_json": {
            "name": "Invalid flow",
            "steps": [
                {"action": "run_arbitrary_shell_command", "cmd": "rm -rf /"},
            ],
        }
    }
    res = client.post("/api/v1/test-cases/validate", json=invalid_def)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0

    # Missing required action fields
    missing_fields_def = {
        "definition_json": {
            "name": "Missing selector",
            "steps": [
                {"action": "click"},  # missing selector
            ],
        }
    }
    res = client.post("/api/v1/test-cases/validate", json=missing_fields_def)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False


def test_test_case_crud_and_run(client):
    # First create project
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "SaaS Platform", "base_url": "https://myapp.com"},
    )
    project_id = proj_res.json()["id"]

    # Create test case
    tc_payload = {
        "project_id": project_id,
        "name": "Navigation test",
        "description": "Tests top navigation links",
        "enabled": True,
        "definition_json": {
            "name": "Navigation test",
            "steps": [
                {"action": "goto", "url": "/home"},
                {"action": "assert_visible", "selector": "nav"},
            ],
        },
    }
    res = client.post("/api/v1/test-cases", json=tc_payload)
    assert res.status_code == 201
    test_case = res.json()
    tc_id = test_case["id"]
    assert test_case["name"] == "Navigation test"
    assert test_case["project_id"] == project_id

    # Enqueue a test run
    run_payload = {
        "test_case_id": tc_id,
        "trigger_type": "manual",
    }
    run_res = client.post("/api/v1/test-runs", json=run_payload)
    assert run_res.status_code == 201
    run_data = run_res.json()
    assert run_data["status"] == RunStatus.QUEUED.value
    assert run_data["test_case_id"] == tc_id
    run_id = run_data["id"]

    # Fetch run
    get_run_res = client.get(f"/api/v1/test-runs/{run_id}")
    assert get_run_res.status_code == 200
    assert get_run_res.json()["id"] == run_id

    # Cancel run
    cancel_res = client.post(f"/api/v1/test-runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == RunStatus.CANCELLED.value


def test_schedule_crud_and_toggle(client):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "Billing App", "base_url": "https://billing.app"},
    )
    project_id = proj_res.json()["id"]

    tc_res = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "name": "Hourly health check",
            "definition_json": {
                "name": "Health check",
                "steps": [{"action": "goto", "url": "/health"}],
            },
        },
    )
    tc_id = tc_res.json()["id"]

    # Create schedule
    sched_payload = {
        "test_case_id": tc_id,
        "interval_seconds": 3600,
        "enabled": True,
    }
    res = client.post("/api/v1/schedules", json=sched_payload)
    assert res.status_code == 201
    sched = res.json()
    sched_id = sched["id"]
    assert sched["enabled"] is True
    assert sched["next_run_at"] is not None

    # Toggle schedule to disabled
    toggle_res = client.post(f"/api/v1/schedules/{sched_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] is False
    assert toggle_res.json()["next_run_at"] is None


def test_artifact_path_traversal_guard(client):
    # Attempt directory traversal attacks on artifacts endpoint
    traversal_res1 = client.get("/api/v1/artifacts/test-run-123/../../etc/passwd")
    assert traversal_res1.status_code in [400, 404]

    traversal_res2 = client.get("/api/v1/artifacts/../../../windows/system.ini")
    assert traversal_res2.status_code in [400, 404]

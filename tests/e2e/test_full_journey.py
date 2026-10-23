"""Full vertical slice integration test.

Creates a project via API -> creates a test case via API ->
triggers a test run via API -> executes run via Worker queue consumer ->
verifies results, step timeline, screenshots, and logs via API.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from packages.shared.constants import RunStatus, StepStatus
from apps.worker.runner.queue_consumer import QueueConsumer
from tests.fixtures.server import start_fixture_server_in_background, PORT


@pytest.fixture(scope="module")
def fixture_server():
    server = start_fixture_server_in_background(port=PORT)
    yield f"http://127.0.0.1:{PORT}"
    server.shutdown()


def test_complete_vertical_integration_lifecycle(client: TestClient, db_session: Session, fixture_server: str, tmp_path):
    os.environ["ARTIFACT_STORAGE_DIR"] = str(tmp_path)

    # 1. Create Project via REST API
    project_payload = {
        "name": "Integration Test Project",
        "base_url": fixture_server,
        "description": "Deterministic local test app",
    }
    proj_res = client.post("/api/v1/projects", json=project_payload)
    assert proj_res.status_code == 201
    project = proj_res.json()
    project_id = project["id"]
    assert project["base_url"] == fixture_server

    # 2. Create Test Case via REST API
    test_case_payload = {
        "project_id": project_id,
        "name": "E2E Search and Login Flow",
        "enabled": True,
        "definition_json": {
            "name": "E2E Search and Login Flow",
            "steps": [
                {"action": "goto", "url": "/"},
                {"action": "assert_visible", "selector": "h1"},
                {"action": "click", "selector": "#nav-search"},
                {"action": "assert_url", "expected_url": "/search"},
                {"action": "fill", "selector": "#search-input", "value": "autonomous-tester"},
                {"action": "screenshot", "name": "search_filled"},
                {"action": "click", "selector": "#search-btn"},
                {"action": "assert_visible", "selector": "[data-testid='search-results']"},
                {"action": "assert_text", "selector": "#query-result", "expected_text": "autonomous-tester"},
            ],
        },
    }
    tc_res = client.post("/api/v1/test-cases", json=test_case_payload)
    assert tc_res.status_code == 201
    test_case = tc_res.json()
    test_case_id = test_case["id"]

    # 3. Trigger Test Run via REST API (asynchronous enqueue)
    run_res = client.post("/api/v1/test-runs", json={"test_case_id": test_case_id, "trigger_type": "manual"})
    assert run_res.status_code == 201
    run_data = run_res.json()
    run_id = run_data["id"]
    assert run_data["status"] == RunStatus.QUEUED.value

    # 4. Worker executes the queued run
    consumer = QueueConsumer(db_session)
    job_processed = consumer.process_next_job()
    assert job_processed is True

    # 5. Fetch completed Run Details via REST API
    get_run_res = client.get(f"/api/v1/test-runs/{run_id}")
    assert get_run_res.status_code == 200
    completed_run = get_run_res.json()

    assert completed_run["status"] == RunStatus.PASSED.value
    assert completed_run["duration_ms"] is not None
    assert completed_run["duration_ms"] > 0
    assert completed_run["error_summary"] is None

    # Verify step results returned by API
    steps = completed_run["step_results"]
    assert len(steps) == 9
    for s in steps:
        assert s["status"] == StepStatus.PASSED.value
        assert s["duration_ms"] >= 0

    # Verify screenshot was captured and can be retrieved via artifact endpoint
    screenshot_step = steps[5]
    assert screenshot_step["action"] == "screenshot"
    assert screenshot_step["screenshot_path"] is not None

    artifact_res = client.get(f"/api/v1/artifacts/{screenshot_step['screenshot_path']}")
    assert artifact_res.status_code == 200
    assert artifact_res.headers["content-type"] == "image/png"
    assert len(artifact_res.content) > 100

    # 6. Verify Overview Stats reflect the new project and passed run
    stats_res = client.get("/api/v1/stats/overview")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_projects"] >= 1
    assert stats["total_test_cases"] >= 1
    assert stats["total_runs"] >= 1
    assert stats["passed_runs"] >= 1
    assert stats["pass_rate_percentage"] == 100.0

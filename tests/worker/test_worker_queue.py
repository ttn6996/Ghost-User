"""Test queue consumer and worker lifecycle."""

import pytest
from sqlalchemy.orm import Session
from app.db.models import Project, TestCase, TestRun
from packages.shared.constants import RunStatus
from apps.worker.runner.queue_consumer import QueueConsumer
from tests.fixtures.server import start_fixture_server_in_background, PORT


@pytest.fixture(scope="module")
def fixture_server():
    server = start_fixture_server_in_background(port=0)
    actual_port = server.server_address[1]
    yield f"http://127.0.0.1:{actual_port}"
    server.shutdown()
    server.server_close()


def test_queue_consumer_claims_and_executes(db_session: Session, fixture_server: str):
    project = Project(name="Queue Test Site", base_url=fixture_server)
    db_session.add(project)
    db_session.commit()

    test_case = TestCase(
        project_id=project.id,
        name="Simple Navigation",
        definition_json={
            "name": "Simple Navigation",
            "steps": [
                {"action": "goto", "url": "/"},
                {"action": "assert_visible", "selector": "h1"},
            ],
        },
    )
    db_session.add(test_case)
    db_session.commit()

    run = TestRun(test_case_id=test_case.id, status=RunStatus.QUEUED.value)
    db_session.add(run)
    db_session.commit()

    consumer = QueueConsumer(db_session)
    processed = consumer.process_next_job()

    assert processed is True
    db_session.refresh(run)
    assert run.status == RunStatus.PASSED.value

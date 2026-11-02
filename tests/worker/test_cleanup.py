"""Unit tests for DataCleanupExecutor (Pillar 4 automated teardown)."""

import pytest
from unittest.mock import MagicMock, patch
from apps.worker.runner.cleanup import DataCleanupExecutor, CleanupReport
from packages.shared.schemas import TestDefinition, GotoAction, FillAction, ClickAction
from packages.shared.data_generator import SyntheticDataGenerator


def test_cleanup_executor_initialization():
    executor = DataCleanupExecutor(run_id="run_12345", allow_local=True)
    assert executor.run_id == "run_12345"
    assert executor.allow_local is True
    assert executor._tracked_entities == []


def test_extract_tagged_values_from_definition():
    data_gen = SyntheticDataGenerator(run_id="run_abc")
    tagged_val1 = data_gen.generate("username", "text")
    tagged_email = data_gen.email()
    normal_val = "just_a_normal_input"

    test_def = TestDefinition(
        name="Test With Mixed Data",
        steps=[
            GotoAction(url="/login"),
            FillAction(selector="#username", value=tagged_val1),
            FillAction(selector="#email", value=tagged_email),
            FillAction(selector="#comment", value=normal_val),
            ClickAction(selector="button[type='submit']"),
        ],
    )

    executor = DataCleanupExecutor(run_id="run_abc", allow_local=True)
    extracted = executor.extract_tagged_values_from_definition(test_def)

    assert tagged_val1 in extracted
    assert tagged_email in extracted
    assert normal_val not in extracted
    assert len(extracted) == 2


def test_execute_teardown_no_data():
    executor = DataCleanupExecutor(run_id="run_empty", allow_local=True)
    test_def = TestDefinition(
        name="No Tagged Data",
        steps=[
            GotoAction(url="/"),
            ClickAction(selector="button"),
        ],
    )
    report = executor.execute_teardown(base_url="http://127.0.0.1:3000", definition=test_def)
    assert report.status == "no_data"
    assert report.total_tagged_items == 0
    assert len(report.log_messages) >= 1
    assert "No synthetic test data tags detected" in report.log_messages[0]


def test_execute_teardown_with_tracked_entities():
    executor = DataCleanupExecutor(run_id="run_test", allow_local=True)
    executor.track_created_entity(
        identifier="AUTOQA_run_test_item_999",
        entity_type="item",
        delete_url="http://127.0.0.1:3000/api/items/999",
        delete_method="DELETE",
    )

    with patch.object(executor, "_perform_http_teardown") as mock_teardown:
        report = executor.execute_teardown(base_url="http://127.0.0.1:3000")
        assert report.total_tagged_items == 1
        assert "AUTOQA_run_test_item_999" in report.purged_items
        assert report.status == "completed"
        mock_teardown.assert_called_once_with(
            "http://127.0.0.1:3000/api/items/999",
            method="DELETE",
            base_url="http://127.0.0.1:3000",
        )


def test_execute_teardown_logs_unpurged_items_for_audit():
    data_gen = SyntheticDataGenerator(run_id="run_audit_only")
    tagged_val = data_gen.generate("product_title", "text")

    test_def = TestDefinition(
        name="Form Input Without Direct Delete Endpoint",
        steps=[
            GotoAction(url="/new-product"),
            FillAction(selector="#title", value=tagged_val),
        ],
    )

    executor = DataCleanupExecutor(run_id="run_audit_only", allow_local=True)
    report = executor.execute_teardown(base_url="http://127.0.0.1:3000", definition=test_def)

    assert report.total_tagged_items == 1
    assert tagged_val in report.pending_items
    assert report.status == "completed"
    assert any("recorded in teardown audit manifest" in m for m in report.log_messages)

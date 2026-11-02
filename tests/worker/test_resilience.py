"""Tests for Pillar 3: Resilient Browser Automation & Self-Healing Locator Engine."""

import pytest
from unittest.mock import MagicMock
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from apps.worker.runner.resilience import (
    wait_for_page_readiness,
    resolve_self_healing_locator,
)


def test_resolve_self_healing_locator_primary_succeeds():
    mock_page = MagicMock()
    mock_loc = MagicMock()
    mock_loc.is_visible.return_value = True
    mock_page.locator.return_value.first = mock_loc

    loc, is_healed, strategy = resolve_self_healing_locator(
        page=mock_page,
        primary_selector="#submit-btn",
        action_type="click",
    )

    assert is_healed is False
    assert strategy == "primary"
    assert loc == mock_loc


def test_resolve_self_healing_locator_heals_button_role():
    mock_page = MagicMock()

    # Primary selector fails
    failing_loc = MagicMock()
    failing_loc.is_visible.side_effect = PlaywrightTimeoutError("timeout")
    mock_page.locator.return_value.first = failing_loc

    # Semantic get_by_role('button') succeeds
    healed_btn = MagicMock()
    healed_btn.is_visible.return_value = True
    mock_page.get_by_role.return_value.first = healed_btn

    loc, is_healed, strategy = resolve_self_healing_locator(
        page=mock_page,
        primary_selector="button.legacy-hash-btn[name='login']",
        action_type="click",
        target_value="Login",
    )

    assert is_healed is True
    assert "role=button" in strategy
    assert loc == healed_btn


def test_resolve_self_healing_locator_heals_input_label_or_placeholder():
    mock_page = MagicMock()

    # Primary selector fails
    failing_loc = MagicMock()
    failing_loc.is_visible.side_effect = PlaywrightTimeoutError("timeout")
    mock_page.locator.return_value.first = failing_loc

    # Semantic get_by_label fails, but get_by_placeholder succeeds
    failing_label = MagicMock()
    failing_label.is_visible.side_effect = PlaywrightTimeoutError("timeout")
    mock_page.get_by_label.return_value.first = failing_label

    healed_ph = MagicMock()
    healed_ph.is_visible.return_value = True
    mock_page.get_by_placeholder.return_value.first = healed_ph

    loc, is_healed, strategy = resolve_self_healing_locator(
        page=mock_page,
        primary_selector="input#unstable-id-492[placeholder='Enter Email']",
        action_type="fill",
        target_value="test@example.com",
    )

    assert is_healed is True
    assert "placeholder=" in strategy
    assert loc == healed_ph


def test_resolve_self_healing_locator_heals_by_text():
    mock_page = MagicMock()

    # Primary selector fails
    failing_loc = MagicMock()
    failing_loc.is_visible.side_effect = PlaywrightTimeoutError("timeout")
    mock_page.locator.return_value.first = failing_loc

    # Role and Label fail
    failing_role = MagicMock()
    failing_role.is_visible.side_effect = PlaywrightTimeoutError("timeout")
    mock_page.get_by_role.return_value.first = failing_role

    # Text succeeds
    healed_txt = MagicMock()
    healed_txt.is_visible.return_value = True
    mock_page.get_by_text.return_value.first = healed_txt

    loc, is_healed, strategy = resolve_self_healing_locator(
        page=mock_page,
        primary_selector="div.custom-clickable:has-text('Proceed')",
        action_type="click",
    )

    assert is_healed is True
    assert "text=" in strategy
    assert loc == healed_txt


def test_wait_for_page_readiness_runs_without_exceptions():
    mock_page = MagicMock()
    spinner_loc = MagicMock()
    spinner_loc.is_visible.return_value = False
    mock_page.locator.return_value.first = spinner_loc

    # Should safely complete without error
    wait_for_page_readiness(mock_page, timeout_ms=500)
    mock_page.wait_for_load_state.assert_called_once_with("domcontentloaded", timeout=500)


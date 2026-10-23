"""Playwright action executors for browser journey steps."""

import time
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from packages.shared.schemas import (
    GotoAction,
    ClickAction,
    FillAction,
    SelectOptionAction,
    CheckAction,
    UncheckAction,
    WaitForVisibleAction,
    AssertVisibleAction,
    AssertTextAction,
    AssertUrlAction,
    ScreenshotAction,
    TestAction,
)
from apps.worker.runner.security import resolve_target_url, SecurityValidationError
from apps.worker.runner.artifacts import ArtifactManager


class StepAssertionFailure(Exception):
    """Explicitly raised when a website state assertion fails."""
    pass


class StepExecutionError(Exception):
    """Raised when the automation engine encounters a runtime or browser error."""
    pass


def execute_action(
    action: TestAction,
    page: Page,
    base_url: str,
    step_index: int,
    artifact_manager: ArtifactManager,
    allow_local: bool = False,
) -> Optional[str]:
    """Executes a single test action. Returns relative screenshot path if a screenshot was taken."""
    timeout = action.timeout_ms or 10000

    try:
        if isinstance(action, GotoAction):
            target_url = resolve_target_url(action.url, base_url, allow_local=allow_local)
            page.goto(target_url, timeout=timeout, wait_until="load")
            return None

        elif isinstance(action, ClickAction):
            locator = page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return None

        elif isinstance(action, FillAction):
            locator = page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.fill(action.value, timeout=timeout)
            return None

        elif isinstance(action, SelectOptionAction):
            locator = page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.select_option(value=action.value, timeout=timeout)
            return None

        elif isinstance(action, CheckAction):
            locator = page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.check(timeout=timeout)
            return None

        elif isinstance(action, UncheckAction):
            locator = page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.uncheck(timeout=timeout)
            return None

        elif isinstance(action, WaitForVisibleAction):
            page.locator(action.selector).first.wait_for(state="visible", timeout=timeout)
            return None

        elif isinstance(action, AssertVisibleAction):
            try:
                locator = page.locator(action.selector).first
                locator.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeoutError:
                raise StepAssertionFailure(f"Assertion failed: Element '{action.selector}' was not visible after {timeout}ms.")
            return None

        elif isinstance(action, AssertTextAction):
            try:
                locator = page.locator(action.selector).first
                locator.wait_for(state="visible", timeout=timeout)
                actual_text = locator.text_content() or ""
                if action.exact:
                    if actual_text.strip() != action.expected_text.strip():
                        raise StepAssertionFailure(
                            f"Assertion failed: Exact text mismatch on '{action.selector}'. "
                            f"Expected '{action.expected_text}', found '{actual_text.strip()}'."
                        )
                else:
                    if action.expected_text not in actual_text:
                        raise StepAssertionFailure(
                            f"Assertion failed: Substring '{action.expected_text}' not found in '{action.selector}'. "
                            f"Found '{actual_text.strip()}'."
                        )
            except PlaywrightTimeoutError:
                raise StepAssertionFailure(f"Assertion failed: Target '{action.selector}' not visible within {timeout}ms to inspect text.")
            return None

        elif isinstance(action, AssertUrlAction):
            current_url = page.url
            if action.expected_url not in current_url:
                raise StepAssertionFailure(
                    f"Assertion failed: Current URL '{current_url}' does not match expected URL '{action.expected_url}'."
                )
            return None

        elif isinstance(action, ScreenshotAction):
            abs_path, rel_path = artifact_manager.get_screenshot_path(step_index, action.name)
            page.screenshot(path=str(abs_path), full_page=True)
            return rel_path

        else:
            raise StepExecutionError(f"Unknown or unsupported action type: {type(action)}")

    except StepAssertionFailure:
        raise
    except SecurityValidationError as e:
        raise StepExecutionError(f"Security validation violation: {e}")
    except PlaywrightTimeoutError as e:
        raise StepExecutionError(f"Browser action timed out after {timeout}ms on action '{action.action}': {e}")
    except Exception as e:
        raise StepExecutionError(f"Browser execution error during '{action.action}': {e}")

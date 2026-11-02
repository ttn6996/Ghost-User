"""Playwright action executors for browser journey steps with Self-Healing Locators."""

import time
from typing import List, Optional
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
from apps.worker.runner.resilience import (
    wait_for_page_readiness,
    resolve_self_healing_locator,
)


class StepAssertionFailure(Exception):
    """Explicitly raised when a website state assertion fails."""
    pass


class StepExecutionError(Exception):
    """Raised when the automation engine encounters a runtime or browser error."""
    pass



def _notify_healing_if_any(page: Page, step_index: int, action_type: str, selector: str, is_healed: bool, strategy: Optional[str]) -> None:
    if is_healed and strategy:
        msg = f"[SELF_HEALED] Step {step_index} ({action_type}): Primary selector '{selector}' failed, recovered via '{strategy}'"
        logger.info(msg)
        try:
            page.evaluate("([m]) => console.warn(m)", [msg])
        except Exception:
            pass

def execute_action(
    action: TestAction,
    page: Page,
    base_url: str,
    step_index: int,
    artifact_manager: ArtifactManager,
    allow_local: bool = False,
    allowed_domains: Optional[List[str]] = None,
) -> Optional[str]:
    """Executes a single test action with self-healing locator fallbacks and spinner synchronization."""
    timeout = action.timeout_ms or 10000

    try:
        if isinstance(action, GotoAction):
            target_url = resolve_target_url(
                action.url,
                base_url,
                allowed_domains=allowed_domains,
                allow_local=allow_local,
            )
            page.goto(target_url, timeout=timeout, wait_until="domcontentloaded")
            wait_for_page_readiness(page)
            return None

        # Synchronize before element interactions
        wait_for_page_readiness(page, timeout_ms=3000)

        if isinstance(action, ClickAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="click", timeout_ms=timeout
            )
            _notify_healing_if_any(page, step_index, "click", action.selector, is_healed, strategy)
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            wait_for_page_readiness(page)
            return None

        elif isinstance(action, FillAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="fill", target_value=action.value, timeout_ms=timeout
            )
            _notify_healing_if_any(page, step_index, "fill", action.selector, is_healed, strategy)
            locator.wait_for(state="visible", timeout=timeout)
            locator.fill(action.value, timeout=timeout)
            return None

        elif isinstance(action, SelectOptionAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="select_option", target_value=action.value, timeout_ms=timeout
            )
            _notify_healing_if_any(page, step_index, "select_option", action.selector, is_healed, strategy)
            locator.wait_for(state="visible", timeout=timeout)
            locator.select_option(value=action.value, timeout=timeout)
            return None

        elif isinstance(action, CheckAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="check", timeout_ms=timeout
            )
            locator.wait_for(state="visible", timeout=timeout)
            locator.check(timeout=timeout)
            return None

        elif isinstance(action, UncheckAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="uncheck", timeout_ms=timeout
            )
            locator.wait_for(state="visible", timeout=timeout)
            locator.uncheck(timeout=timeout)
            return None

        elif isinstance(action, WaitForVisibleAction):
            locator, is_healed, strategy = resolve_self_healing_locator(
                page, action.selector, action_type="wait", timeout_ms=timeout
            )
            locator.wait_for(state="visible", timeout=timeout)
            return None

        elif isinstance(action, AssertVisibleAction):
            try:
                locator, is_healed, strategy = resolve_self_healing_locator(
                    page, action.selector, action_type="assert_visible", timeout_ms=timeout
                )
                _notify_healing_if_any(page, step_index, "assert_visible", action.selector, is_healed, strategy)
                locator.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeoutError:
                raise StepAssertionFailure(f"Assertion failed: Element '{action.selector}' was not visible after {timeout}ms.")
            return None

        elif isinstance(action, AssertTextAction):
            try:
                locator, is_healed, strategy = resolve_self_healing_locator(
                    page, action.selector, action_type="assert_text", timeout_ms=timeout
                )
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
            expected = action.expected_url
            actual = page.url
            if expected.startswith("/"):
                # Path matching
                from urllib.parse import urlparse
                actual_path = urlparse(actual).path
                if actual_path != expected and not actual_path.endswith(expected):
                    raise StepAssertionFailure(
                        f"Assertion failed: URL path mismatch. Expected path '{expected}', current URL '{actual}'."
                    )
            else:
                if actual != expected and not actual.startswith(expected):
                    raise StepAssertionFailure(
                        f"Assertion failed: URL mismatch. Expected '{expected}', found '{actual}'."
                    )
            return None

        elif isinstance(action, ScreenshotAction):
            abs_path, rel_path = artifact_manager.get_screenshot_path(step_index, action.name)
            page.screenshot(path=str(abs_path), full_page=True)
            return rel_path

        else:
            raise StepExecutionError(f"Unsupported action type: {action.action}")

    except (StepAssertionFailure, SecurityValidationError):
        raise
    except PlaywrightTimeoutError as e:
        raise StepExecutionError(f"Browser action timeout after {timeout}ms: {e}")
    except Exception as e:
        raise StepExecutionError(f"Browser action failed: {e}")

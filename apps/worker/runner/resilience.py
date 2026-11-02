"""Resilient Browser Automation & Self-Healing Locator Engine.

Implements Pillar 3:
1. Self-healing locators using Playwright accessibility tree (role, name, placeholder, label)
   when dynamic CSS classes or obfuscated DOM IDs change between builds.
2. Spinner & Async synchronization waiting for loading indicators, skeletons, and network idle.
"""

import re
import time
from typing import Optional, Tuple, List
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

from app.core.logging import logger


COMMON_SPINNER_SELECTORS = [
    "[aria-busy='true']",
    "[role='progressbar']",
    ".spinner",
    ".loading",
    ".skeleton",
    ".ant-spin",
    ".chakra-spinner",
    ".v-spinner",
    "svg.animate-spin",
]


def wait_for_page_readiness(page: Page, timeout_ms: int = 4000) -> None:
    """Waits for network stabilization and ensures common loading spinners have detached/hidden."""
    try:
        # Give page a short window to settle
        page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 3000))
    except Exception:
        pass

    # Check for active spinners and wait for them to disappear
    deadline = time.time() + (timeout_ms / 1000.0)
    for selector in COMMON_SPINNER_SELECTORS:
        try:
            spinner = page.locator(selector).first
            if spinner.is_visible(timeout=200):
                remaining_ms = int(max(0.1, deadline - time.time()) * 1000)
                spinner.wait_for(state="hidden", timeout=min(remaining_ms, 2500))
        except Exception:
            continue


def resolve_self_healing_locator(
    page: Page,
    primary_selector: str,
    action_type: str = "click",
    target_value: Optional[str] = None,
    timeout_ms: int = 3000,
) -> Tuple[Locator, bool, str]:
    """Attempts to find the target element using primary selector.
    
    If primary selector fails or times out, activates semantic fallbacks
    (Accessibility role, text matching, aria labels, placeholder) to self-heal.
    
    Returns: (Locator, is_healed: bool, strategy_used: str)
    """
    # 1. Try primary selector first
    try:
        loc = page.locator(primary_selector).first
        if loc.is_visible(timeout=timeout_ms):
            return loc, False, "primary"
    except Exception:
        pass

    logger.warning(f"[SELF_HEALING] Primary selector '{primary_selector}' failed for action '{action_type}'. Attempting semantic recovery...")

    # 2. Extract keywords from primary selector or target value
    # e.g., "button.submit-v2#btn-submit" -> "submit"
    candidate_names: List[str] = []
    if target_value and len(target_value) < 50:
        candidate_names.append(target_value)

    # Extract text from selector like: button:has-text('Submit') or [name='username']
    text_match = re.search(r"""(?:text=|has-text\()['"]?([^'")]+)['"]?""", primary_selector, re.IGNORECASE)
    if text_match:
        candidate_names.append(text_match.group(1))

    attr_match = re.search(r"""\[(?:name|id|placeholder|aria-label)=['"]?([^'"]+)['"]?\]""", primary_selector, re.IGNORECASE)
    if attr_match:
        candidate_names.append(attr_match.group(1))

    # Strip css classes/hashes to find base word
    clean_words = re.findall(r"[a-zA-Z]{3,}", primary_selector)
    for w in clean_words:
        if w.lower() not in ("button", "input", "form", "div", "span", "class", "type", "first", "last"):
            candidate_names.append(w)

    # 3. Strategy A: Semantic Role Fallback
    if action_type in ("click", "check", "uncheck"):
        for name in candidate_names:
            try:
                btn_loc = page.get_by_role("button", name=name, exact=False).first
                if btn_loc.is_visible(timeout=1000):
                    logger.info(f"[SELF_HEALED] Successfully recovered button element via role='button', name='{name}'")
                    return btn_loc, True, f"role=button[name='{name}']"
            except Exception:
                pass

            try:
                link_loc = page.get_by_role("link", name=name, exact=False).first
                if link_loc.is_visible(timeout=1000):
                    logger.info(f"[SELF_HEALED] Successfully recovered link element via role='link', name='{name}'")
                    return link_loc, True, f"role=link[name='{name}']"
            except Exception:
                pass

    # 4. Strategy B: Form Input Field Fallbacks (for Fill / SelectOption)
    if action_type in ("fill", "select_option"):
        for name in candidate_names:
            try:
                inp_loc = page.get_by_label(name, exact=False).first
                if inp_loc.is_visible(timeout=1000):
                    logger.info(f"[SELF_HEALED] Successfully recovered input via label='{name}'")
                    return inp_loc, True, f"label='{name}'"
            except Exception:
                pass

            try:
                ph_loc = page.get_by_placeholder(name, exact=False).first
                if ph_loc.is_visible(timeout=1000):
                    logger.info(f"[SELF_HEALED] Successfully recovered input via placeholder='{name}'")
                    return ph_loc, True, f"placeholder='{name}'"
            except Exception:
                pass

    # 5. Strategy C: Text Content Matching
    for name in candidate_names:
        try:
            txt_loc = page.get_by_text(name, exact=False).first
            if txt_loc.is_visible(timeout=1000):
                logger.info(f"[SELF_HEALED] Successfully recovered element via visible text='{name}'")
                return txt_loc, True, f"text='{name}'"
        except Exception:
            pass

    # 6. Fallback to primary locator (will raise proper Playwright timeout with context)
    return page.locator(primary_selector).first, False, "primary_failed"


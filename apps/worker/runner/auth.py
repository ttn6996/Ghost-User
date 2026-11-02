"""Authentication & Session Injection Manager for Ghost-User.

Implements Pillar 2: Session Injection & Multi-Role Authentication.
Allows automated journeys and web crawlers to seamlessly test protected routes
by pre-authenticating via:
1. HTTP Headers & Bearer Tokens
2. Cookies (session IDs, JWT cookies)
3. LocalStorage / SessionStorage tokens
4. Deterministic Auto-Login journeys
"""

import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger("ghost-user")


def inject_auth_profile(
    context: BrowserContext,
    page: Page,
    base_url: str,
    auth_profile: Optional[Dict[str, Any]],
) -> None:
    """Injects cookies, headers, storage items, or performs auto-login into Playwright context."""
    if not auth_profile or not isinstance(auth_profile, dict):
        return

    # 1. Extra HTTP Headers / Bearer Tokens
    headers = auth_profile.get("headers")
    if headers and isinstance(headers, dict):
        clean_headers = {str(k): str(v) for k, v in headers.items() if v is not None}
        if clean_headers:
            context.set_extra_http_headers(clean_headers)

    # 2. Cookies injection
    cookies = auth_profile.get("cookies")
    if cookies and isinstance(cookies, list):
        parsed = urlparse(base_url)
        default_domain = parsed.hostname or "localhost"
        valid_cookies = []
        for c in cookies:
            if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                valid_cookies.append({
                    "name": str(c["name"]),
                    "value": str(c["value"]),
                    "domain": str(c.get("domain") or default_domain),
                    "path": str(c.get("path") or "/"),
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "secure": bool(c.get("secure", False)),
                })
        if valid_cookies:
            try:
                context.add_cookies(valid_cookies)
                logger.info(f"Injected {len(valid_cookies)} session cookies into browser context")
            except Exception as e:
                logger.warning(f"Could not inject session cookies: {e}")

    # 3. LocalStorage injection via init script
    storage = auth_profile.get("local_storage")
    if storage and isinstance(storage, list):
        for item in storage:
            if isinstance(item, dict) and item.get("key") and item.get("value") is not None:
                k_json = json.dumps(str(item["key"]))
                v_json = json.dumps(str(item["value"]))
                page.add_init_script(f"""
                    try {{
                        localStorage.setItem({k_json}, {v_json});
                    }} catch(e) {{}}
                """)

    # 4. Auto-Login Sequence (if enabled)
    auto_login = auth_profile.get("auto_login")
    if auto_login and isinstance(auto_login, dict) and auto_login.get("enabled"):
        login_rel = auto_login.get("login_url", "/login")
        target_login_url = urljoin(base_url.rstrip("/") + "/", login_rel.lstrip("/"))
        u_sel = auto_login.get("username_selector", "#username, input[name='username'], input[type='text']")
        u_val = auto_login.get("username_value", "")
        p_sel = auto_login.get("password_selector", "#password, input[name='password'], input[type='password']")
        p_val = auto_login.get("password_value", "")
        btn_sel = auto_login.get("submit_selector", "button[type='submit'], button:has-text('Login'), button:has-text('Đăng nhập')")

        try:
            logger.info(f"Executing pre-flight auto-login at {target_login_url}")
            page.goto(target_login_url, wait_until="domcontentloaded", timeout=12000)
            if u_val:
                page.fill(u_sel, u_val, timeout=6000)
            if p_val:
                page.fill(p_sel, p_val, timeout=6000)
            page.click(btn_sel, timeout=6000)
            page.wait_for_timeout(2000)
            logger.info("Pre-flight auto-login successfully dispatched")
        except Exception as e:
            logger.warning(f"Pre-flight auto-login notice: {e}")


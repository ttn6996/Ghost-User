"""Autonomous Web Crawler & Discovery Engine for Ghost-User.

Crawl a website starting from its base URL, discover pages, forms,
interactive elements, broken links (404/500), and auto-synthesize
ready-to-run Ghost-User test cases.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Error as PlaywrightError

from app.core.config import settings
from apps.worker.runner.security import (
    check_browser_request_security,
    get_effective_allow_local,
    resolve_and_validate_host,
    resolve_target_url,
)
from packages.shared.schemas import TestDefinition

logger = logging.getLogger("ghost-user")


class WebCrawler:
    """Discovers website structure and auto-generates test suites."""

    def __init__(
        self,
        base_url: str,
        max_pages: int = 15,
        max_depth: int = 2,
        allow_local: Optional[bool] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_pages = min(max(max_pages, 1), 30)
        self.max_depth = min(max(max_depth, 1), 3)
        self.allow_local = get_effective_allow_local(allow_local)

        parsed_base = urlparse(self.base_url)
        self.base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        self.base_netloc = parsed_base.netloc

    def crawl(self) -> Dict[str, Any]:
        """Runs the crawler and returns discovered pages, forms, issues, and generated tests."""
        logger.info(f"Starting auto-discovery crawl on {self.base_url} (max_pages={self.max_pages}, max_depth={self.max_depth})")

        # Validate base host security
        parsed_base = urlparse(self.base_url)
        resolve_and_validate_host(parsed_base.hostname or "", allow_local=self.allow_local)

        visited_urls: Set[str] = set()
        queue: List[Tuple[str, int]] = [(self.base_url, 0)]
        crawled_pages: List[Dict[str, Any]] = []
        broken_links: List[Dict[str, Any]] = []
        forms_detected: List[Dict[str, Any]] = []
        console_errors: List[Dict[str, Any]] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=False,
            )

            # Security route interception
            def handle_route(route):
                req = route.request
                is_nav = req.is_navigation_request()
                is_allowed, reason = check_browser_request_security(
                    url=req.url,
                    base_url=self.base_url,
                    is_navigation=is_nav,
                    allow_local=self.allow_local,
                )
                if not is_allowed:
                    logger.debug(f"Crawler security blocked request to {req.url}: {reason}")
                    route.abort("blockedbyclient")
                else:
                    route.continue_()

            context.route("**/*", handle_route)

            page = context.new_page()
            page.set_default_timeout(15000)

            # Capture console errors
            page.on("console", lambda msg: console_errors.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
            }) if msg.type == "error" else None)

            while queue and len(visited_urls) < self.max_pages:
                current_url, depth = queue.pop(0)

                clean_url, _ = urldefrag(current_url)
                if clean_url in visited_urls:
                    continue

                visited_urls.add(clean_url)
                logger.info(f"Crawler visiting [{len(visited_urls)}/{self.max_pages}]: {clean_url} (depth={depth})")

                try:
                    response = page.goto(clean_url, wait_until="domcontentloaded", timeout=12000)
                    status_code = response.status if response else 200

                    # Check for broken links (4xx, 5xx)
                    if status_code >= 400:
                        broken_links.append({
                            "url": clean_url,
                            "status_code": status_code,
                            "depth": depth,
                        })
                        crawled_pages.append({
                            "url": clean_url,
                            "path": urlparse(clean_url).path or "/",
                            "title": "Error Page",
                            "status_code": status_code,
                            "forms_count": 0,
                            "links_found": 0,
                            "is_broken": True,
                        })
                        continue

                    page_title = page.title() or "Untitled Page"
                    path = urlparse(clean_url).path or "/"

                    # 1. Discover Links
                    links_on_page: List[str] = []
                    href_elements = page.query_selector_all("a[href]")
                    for el in href_elements:
                        raw_href = el.get_attribute("href")
                        if not raw_href or raw_href.startswith("#") or raw_href.startswith("javascript:") or raw_href.startswith("mailto:"):
                            continue

                        full_link = urljoin(clean_url, raw_href)
                        clean_link, _ = urldefrag(full_link)
                        parsed_link = urlparse(clean_link)

                        # Confine to same origin
                        if parsed_link.netloc == self.base_netloc:
                            links_on_page.append(clean_link)
                            if clean_link not in visited_urls and depth + 1 <= self.max_depth:
                                if not any(item[0] == clean_link for item in queue):
                                    queue.append((clean_link, depth + 1))

                    # 2. Discover Forms & Interactive Elements
                    page_forms = self._inspect_page_forms(page, clean_url, path)
                    for pf in page_forms:
                        forms_detected.append(pf)

                    crawled_pages.append({
                        "url": clean_url,
                        "path": path,
                        "title": page_title,
                        "status_code": status_code,
                        "forms_count": len(page_forms),
                        "links_found": len(links_on_page),
                        "is_broken": False,
                    })

                except Exception as e:
                    logger.warning(f"Error crawling {clean_url}: {e}")
                    broken_links.append({
                        "url": clean_url,
                        "status_code": 0,
                        "error": str(e),
                        "depth": depth,
                    })

            browser.close()

        # Synthesize smart test cases
        suggested_tests = self._synthesize_test_cases(crawled_pages, forms_detected, broken_links)

        return {
            "base_url": self.base_url,
            "pages_count": len(crawled_pages),
            "broken_links_count": len(broken_links),
            "forms_count": len(forms_detected),
            "pages": crawled_pages,
            "broken_links": broken_links,
            "forms": forms_detected,
            "console_errors": console_errors,
            "suggested_tests": suggested_tests,
        }

    def _inspect_page_forms(self, page: Page, page_url: str, path: str) -> List[Dict[str, Any]]:
        """Inspects DOM for forms, inputs, and submit buttons."""
        forms_found: List[Dict[str, Any]] = []

        try:
            form_elements = page.query_selector_all("form")
            if form_elements:
                for idx, f_el in enumerate(form_elements):
                    inputs = []
                    for inp in f_el.query_selector_all("input, textarea, select"):
                        name = inp.get_attribute("name") or ""
                        inp_id = inp.get_attribute("id") or ""
                        inp_type = (inp.get_attribute("type") or "text").lower()
                        placeholder = inp.get_attribute("placeholder") or ""
                        inputs.append({
                            "name": name,
                            "id": inp_id,
                            "type": inp_type,
                            "placeholder": placeholder,
                        })

                    buttons = []
                    for btn in f_el.query_selector_all("button, input[type='submit']"):
                        b_type = (btn.get_attribute("type") or "submit").lower()
                        b_text = (btn.inner_text() or "").strip()
                        buttons.append({
                            "type": b_type,
                            "text": b_text,
                        })

                    form_type = self._classify_form(inputs, path)
                    forms_found.append({
                        "page_path": path,
                        "page_url": page_url,
                        "form_type": form_type,
                        "inputs": inputs,
                        "buttons": buttons,
                    })
            else:
                # Standalone inputs if not wrapped in <form>
                standalone_inputs = page.query_selector_all("input")
                if standalone_inputs:
                    inputs = []
                    for inp in standalone_inputs:
                        name = inp.get_attribute("name") or ""
                        inp_id = inp.get_attribute("id") or ""
                        inp_type = (inp.get_attribute("type") or "text").lower()
                        if inp_type not in ("hidden", "checkbox", "radio"):
                            inputs.append({
                                "name": name,
                                "id": inp_id,
                                "type": inp_type,
                                "placeholder": inp.get_attribute("placeholder") or "",
                            })

                    if inputs:
                        form_type = self._classify_form(inputs, path)
                        forms_found.append({
                            "page_path": path,
                            "page_url": page_url,
                            "form_type": form_type,
                            "inputs": inputs,
                            "buttons": [{"type": "button", "text": "Submit"}],
                        })
        except Exception as e:
            logger.debug(f"Form inspection notice for {path}: {e}")

        return forms_found

    def _classify_form(self, inputs: List[Dict[str, str]], path: str) -> str:
        """Determines the semantic category of a form."""
        types = [i.get("type", "") for i in inputs]
        names = [i.get("name", "").lower() for i in inputs] + [i.get("id", "").lower() for i in inputs]

        if "password" in types or any("pass" in n for n in names):
            if "register" in path or any(k in names for k in ["fullname", "birth", "confirm"]):
                return "Registration Form"
            return "Login Form"

        if any(k in names for k in ["q", "query", "search", "keyword"]) or any("tìm" in i.get("placeholder", "").lower() for i in inputs):
            return "Search Form"

        return "General Form"

    def _synthesize_test_cases(
        self,
        crawled_pages: List[Dict[str, Any]],
        forms: List[Dict[str, Any]],
        broken_links: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Auto-generates high-value, executable test definitions based on crawl findings."""
        suggested: List[Dict[str, Any]] = []

        # 1. Sitemap Smoke Test (All discovered healthy public pages)
        healthy_pages = [p for p in crawled_pages if not p.get("is_broken", False)]
        if healthy_pages:
            smoke_steps = []
            sample_pages = healthy_pages[:5] # Test top 5 pages
            for p in sample_pages:
                smoke_steps.append({"action": "goto", "url": p["path"]})
                smoke_steps.append({"action": "assert_visible", "selector": "body"})
                smoke_steps.append({"action": "screenshot", "name": f"page_{p['path'].strip('/').replace('/', '_') or 'home'}"})

            suggested.append({
                "name": "Auto-Discovery: Sitemap Smoke Test",
                "description": f"Verifies page load and document visibility across {len(sample_pages)} key discovered site pages.",
                "steps": smoke_steps,
            })

        # 2. Form Tests (Login / Search / General)
        for form in forms:
            ftype = form.get("form_type", "")
            fpath = form.get("page_path", "/")

            if ftype == "Login Form":
                # Find username and password selector
                u_input = next((i for i in form["inputs"] if i.get("type") != "password"), None)
                p_input = next((i for i in form["inputs"] if i.get("type") == "password"), None)

                u_sel = f"#{u_input['id']}" if u_input and u_input.get("id") else (f"input[name='{u_input['name']}']" if u_input and u_input.get("name") else "#username, input[type='text']")
                p_sel = f"#{p_input['id']}" if p_input and p_input.get("id") else (f"input[name='{p_input['name']}']" if p_input and p_input.get("name") else "#password, input[type='password']")

                steps = [
                    {"action": "goto", "url": fpath},
                    {"action": "fill", "selector": u_sel, "value": "user01"},
                    {"action": "fill", "selector": p_sel, "value": "admin123"},
                    {"action": "click", "selector": "button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')"},
                    {"action": "screenshot", "name": "discovered_login_result"},
                ]
                suggested.append({
                    "name": f"Auto-Discovery: Form Test ({fpath})",
                    "description": f"Discovered Login Form at {fpath} with targeted input selectors ({u_sel}, {p_sel}).",
                    "steps": steps,
                })

            elif ftype == "Search Form":
                q_input = form["inputs"][0] if form["inputs"] else None
                q_sel = f"#{q_input['id']}" if q_input and q_input.get("id") else (f"input[name='{q_input['name']}']" if q_input and q_input.get("name") else "input[type='search'], input[name='search'], input[name='q']")

                steps = [
                    {"action": "goto", "url": fpath},
                    {"action": "fill", "selector": q_sel, "value": "test"},
                    {"action": "click", "selector": "button[type='submit'], [data-testid='search-button'], button:has-text('Tìm')"},
                    {"action": "screenshot", "name": "discovered_search_result"},
                ]
                suggested.append({
                    "name": f"Auto-Discovery: Search Test ({fpath})",
                    "description": f"Discovered Search Form at {fpath} with selector ({q_sel}).",
                    "steps": steps,
                })

        # Validate all suggested tests against TestDefinition
        valid_suggested = []
        for t in suggested:
            try:
                TestDefinition.model_validate(t)
                valid_suggested.append(t)
            except Exception as e:
                logger.warning(f"Skipping invalid generated test '{t.get('name')}': {e}")

        return valid_suggested

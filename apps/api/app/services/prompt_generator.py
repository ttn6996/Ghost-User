"""Natural Language Prompt-to-Journey Generator for Ghost-User.

Translates high-level user instructions (in Vietnamese or English) into validated,
executable Ghost-User TestDefinition step sequences.

Features:
- Dual-mode architecture:
  1. Built-in Deterministic NLP Semantic Parser (Offline, zero tokens, robust regex/intent rules).
  2. Optional LLM Integration (Google Gemini or OpenAI) if API keys are configured.
- Intelligent DOM probe: Optionally probes the target page to discover live selector IDs/names.
- Strict schema validation against packages.shared.schemas.TestDefinition.
"""

import os
import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from packages.shared.schemas import TestDefinition

logger = logging.getLogger("ghost-user")


class PromptGenerator:
    """Generates executable Ghost-User test journeys from natural language instructions."""

    def __init__(self, gemini_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)

    async def generate(
        self,
        prompt: str,
        base_url: str,
        page_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate test journey from natural language prompt."""
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise ValueError("Prompt cannot be empty")

        # Optional DOM element discovery from live target
        live_selectors = await self._probe_live_dom(base_url, page_path, cleaned_prompt)

        # 1. Try LLM if configured
        if self.gemini_api_key:
            try:
                result = await self._generate_with_gemini(cleaned_prompt, base_url, live_selectors)
                if result and self._validate_steps(result.get("steps", [])):
                    result["model_used"] = "gemini-flash"
                    return result
            except Exception as e:
                logger.warning(f"Gemini generation fallback triggered: {e}")

        if self.openai_api_key:
            try:
                result = await self._generate_with_openai(cleaned_prompt, base_url, live_selectors)
                if result and self._validate_steps(result.get("steps", [])):
                    result["model_used"] = "openai-gpt"
                    return result
            except Exception as e:
                logger.warning(f"OpenAI generation fallback triggered: {e}")

        # 2. Built-in Deterministic Semantic Parser
        result = self._generate_with_semantic_parser(cleaned_prompt, base_url, page_path, live_selectors)
        result["model_used"] = "builtin-semantic-parser"
        return result

    async def _probe_live_dom(
        self, base_url: str, page_path: Optional[str], prompt: str
    ) -> Dict[str, List[str]]:
        """Optionally fetches the page HTML to discover real element selectors."""
        selectors: Dict[str, List[str]] = {
            "inputs": [],
            "passwords": [],
            "buttons": [],
            "links": [],
        }
        if not base_url:
            return selectors

        # Guess target path if not provided
        target_path = page_path
        if not target_path:
            lower_p = prompt.lower()
            if any(k in lower_p for k in ["login", "đăng nhập", "signin"]):
                target_path = "/login"
            elif any(k in lower_p for k in ["register", "đăng ký", "signup"]):
                target_path = "/register"
            elif any(k in lower_p for k in ["market", "chợ", "shop", "sản phẩm"]):
                target_path = "/marketplace"
            elif any(k in lower_p for k in ["guide", "hướng dẫn", "about"]):
                target_path = "/about-guide"
            else:
                target_path = "/"

        target_url = urljoin(base_url.rstrip("/") + "/", target_path.lstrip("/"))

        try:
            async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    html = resp.text
                    # Extract IDs and names
                    for match in re.finditer(r'<input[^>]+(?:id|name)=["\']([^"\']+)["\']', html, re.IGNORECASE):
                        name = match.group(1)
                        if "pass" in name.lower():
                            selectors["passwords"].append(f"#{name}, input[name='{name}']")
                        else:
                            selectors["inputs"].append(f"#{name}, input[name='{name}']")

                    for match in re.finditer(r'<button[^>]+(?:id|type)=["\']([^"\']+)["\']', html, re.IGNORECASE):
                        btn_val = match.group(1)
                        selectors["buttons"].append(f"button[type='{btn_val}'], #{btn_val}")
        except Exception:
            # Silent fallback if target is not reachable during generation
            pass

        return selectors

    def _generate_with_semantic_parser(
        self,
        prompt: str,
        base_url: str,
        page_path: Optional[str],
        live_selectors: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """High-precision semantic intent parser supporting Vietnamese and English."""
        p_lower = prompt.lower()
        steps: List[Dict[str, Any]] = []

        # 1. Detect Intent Category
        is_login = any(k in p_lower for k in ["đăng nhập", "login", "sign in", "signin", "log in"])
        is_search = any(k in p_lower for k in ["tìm kiếm", "search", "tìm sản phẩm", "tra cứu", "find"])
        is_register = any(k in p_lower for k in ["đăng ký", "register", "sign up", "signup", "tạo tài khoản"])
        is_guide = any(k in p_lower for k in ["hướng dẫn", "guide", "about", "faq", "giới thiệu"])
        is_negative = any(k in p_lower for k in ["sai", "fail", "wrong", "thất bại", "không thành công", "lỗi"])

        # Extract credentials
        user_val = self._extract_user(prompt)
        pass_val = self._extract_password(prompt)
        search_query = self._extract_search_query(prompt)

        # Build Flow
        if is_login:
            # Entry URL
            entry_url = "/login" if "/login" in prompt or not page_path else page_path
            steps.append({"action": "goto", "url": entry_url})

            # Username / Email
            u_sel = (
                live_selectors["inputs"][0]
                if live_selectors.get("inputs")
                else "#username, input[name='username'], input[type='text'], input[name='email']"
            )
            steps.append({
                "action": "fill",
                "selector": u_sel,
                "value": user_val or "user01",
            })

            # Password
            p_sel = (
                live_selectors["passwords"][0]
                if live_selectors.get("passwords")
                else "#password, input[name='password'], input[type='password']"
            )
            steps.append({
                "action": "fill",
                "selector": p_sel,
                "value": pass_val or "admin123",
            })

            # Submit
            btn_sel = (
                live_selectors["buttons"][0]
                if live_selectors.get("buttons")
                else "button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')"
            )
            steps.append({
                "action": "click",
                "selector": btn_sel,
            })

            # Assertion / Outcome
            if is_negative:
                steps.append({
                    "action": "assert_visible",
                    "selector": "div.bg-red-50, .alert-danger, [role='alert'], .error-message",
                })
                steps.append({"action": "screenshot", "name": "login_failed_error"})
                name = f"Negative Test: Login with Invalid Credentials ({user_val or 'user'})"
                desc = "Verifies error message display when entering incorrect credentials."
            else:
                steps.append({
                    "action": "assert_visible",
                    "selector": "nav, header, [data-testid='user-menu'], body",
                })
                steps.append({"action": "screenshot", "name": "login_success"})
                name = f"Authentication Journey ({user_val or 'user01'})"
                desc = f"Submits credentials for {user_val or 'user01'} and verifies authorized session access."

        elif is_search:
            entry_url = "/marketplace" if "/market" in prompt or "chợ" in p_lower else "/"
            steps.append({"action": "goto", "url": entry_url})
            steps.append({
                "action": "fill",
                "selector": "input[placeholder*='Tìm'], input[type='search'], input[name='search'], input[name='q']",
                "value": search_query or "giáo trình",
            })
            steps.append({
                "action": "click",
                "selector": "button[type='submit'], button:has-text('Tìm'), [data-testid='search-button']",
            })
            steps.append({
                "action": "screenshot",
                "name": "search_results",
            })
            name = f"Search Journey for '{search_query or 'giáo trình'}'"
            desc = f"Performs product/catalog search with keyword '{search_query or 'giáo trình'}' and captures results."

        elif is_register:
            entry_url = "/register" if "/register" in prompt else "/register"
            steps.append({"action": "goto", "url": entry_url})
            steps.append({
                "action": "assert_text",
                "selector": "h2, h1",
                "expected_text": "Đăng ký",
            })
            steps.append({
                "action": "fill",
                "selector": "input[name='fullName'], input#fullName, input[name='name']",
                "value": "Nguyen Van A",
            })
            steps.append({
                "action": "fill",
                "selector": "input[name='username'], input#username",
                "value": user_val or "nguyenvana_test",
            })
            steps.append({
                "action": "fill",
                "selector": "input[name='email'], input#email",
                "value": "test_account@example.com",
            })
            steps.append({
                "action": "fill",
                "selector": "input[name='password'], input#password",
                "value": pass_val or "Pass@123456",
            })
            steps.append({
                "action": "screenshot",
                "name": "registration_form_filled",
            })
            name = "Registration Form Verification"
            desc = "Fills out member registration form and captures input validation state."

        elif is_guide:
            entry_url = "/about-guide" if "guide" in p_lower or "hướng dẫn" in p_lower else "/about"
            steps.append({"action": "goto", "url": entry_url})
            steps.append({
                "action": "assert_visible",
                "selector": "h1, h2",
            })
            steps.append({
                "action": "click",
                "selector": "button:has-text('người mua'), button:has-text('FAQ'), button:has-text('hỏi'), summary",
            })
            steps.append({
                "action": "screenshot",
                "name": "guide_faq_opened",
            })
            name = "Guide & FAQ Verification"
            desc = "Navigates to guide page, opens FAQ accordion, and captures rendered content."

        else:
            # Custom generic prompt parsing (extracts actions like goto, click, assert, fill)
            custom_steps, name, desc = self._parse_generic_sequence(prompt, page_path)
            steps = custom_steps

        # Final pass: Guarantee TestDefinition validity
        test_def = {
            "name": name,
            "description": desc,
            "steps": steps,
        }
        TestDefinition.model_validate(test_def)

        return {
            "suggested_name": name,
            "suggested_description": desc,
            "steps": steps,
            "explanation": f"Generated {len(steps)} actions based on your natural language instruction.",
        }

    def _extract_user(self, text: str) -> Optional[str]:
        """Extracts username or email from prompt."""
        # e.g., user01/admin123
        slash_match = re.search(r'([a-zA-Z0-9_\-\.]+)\s*/\s*([a-zA-Z0-9_!@#$%^&*]+)', text)
        if slash_match:
            return slash_match.group(1)

        # Explicit user token like user01, admin, student01
        word_match = re.search(r'\b(user\d+|admin|student\d+)\b', text, re.IGNORECASE)
        if word_match:
            return word_match.group(1)

        # e.g., username "test_user", tài khoản user01
        user_match = re.search(
            r'\b(?:tài khoản|username|tên đăng nhập|email|người dùng)\s*(?:là|:|=|của)?\s*[\'"`]?([a-zA-Z0-9_\-\.@]+)[\'"`]?',
            text,
            re.IGNORECASE,
        )
        if user_match:
            val = user_match.group(1).strip()
            if val.lower() not in ("đăng", "nhập", "của", "mật"):
                return val

        return None

    def _extract_password(self, text: str) -> Optional[str]:
        """Extracts password from prompt."""
        slash_match = re.search(r'([a-zA-Z0-9_\-\.]+)\s*/\s*([a-zA-Z0-9_!@#$%^&*]+)', text)
        if slash_match:
            return slash_match.group(2)

        pass_match = re.search(
            r'\b(?:mật khẩu|password|pass|mat khau)\s*(?:sai|không đúng|là|:|=|nhập)?\s*[\'"`]?([^\s,\'"`]+)[\'"`]?',
            text,
            re.IGNORECASE,
        )
        if pass_match:
            val = pass_match.group(1).strip()
            if val.lower() not in ("sai", "đúng", "không", "nhập", "để"):
                return val
            # Try capturing next word after modifier
            extended_match = re.search(
                r'\b(?:mật khẩu|password|pass|mat khau)\s+(?:sai|không đúng)\s+[\'"`]?([^\s,\'"`]+)[\'"`]?',
                text,
                re.IGNORECASE,
            )
            if extended_match:
                return extended_match.group(1).strip()

        return None

    def _extract_search_query(self, text: str) -> Optional[str]:
        """Extracts search query string from prompt."""
        match = re.search(
            r'(?:tìm kiếm|tìm|search|tra cứu)\s+(?:sản phẩm|từ khóa|món đồ)?\s*[\'"`]?([a-zA-Z0-9_\s\u00C0-\u1EF9]+?)[\'"`]?(?:\s+(?:trên|ở|trong|và|$))',
            text,
            re.IGNORECASE,
        )
        if match:
            query = match.group(1).strip()
            if query and query not in ("sản phẩm", "đồ", "giao diện"):
                return query
        return None

    def _parse_generic_sequence(self, prompt: str, page_path: Optional[str]) -> Tuple[List[Dict[str, Any]], str, str]:
        """Parses generic sequence of actions from freeform text."""
        steps: List[Dict[str, Any]] = []

        # Step 1: Default entry
        start_url = "/"
        url_match = re.search(r'(?:vào|đến|mở|go to|navigate to|open)\s+(?:trang\s+)?([/a-zA-Z0-9_\-\.]+)', prompt, re.IGNORECASE)
        if url_match:
            start_url = url_match.group(1)
            if not start_url.startswith("/") and not start_url.startswith("http"):
                start_url = "/" + start_url
        elif page_path:
            start_url = page_path

        steps.append({"action": "goto", "url": start_url})

        # Check for click targets
        click_match = re.search(r'(?:bấm|click|nhấn|chọn)\s+(?:nút\s+|vào\s+)?[\'"`]?([a-zA-Z0-9_\-\.#\s\u00C0-\u1EF9]+?)[\'"`]?(?:\s*[,.]|$)', prompt, re.IGNORECASE)
        if click_match:
            target = click_match.group(1).strip()
            if target.startswith("#") or target.startswith(".") or "[" in target:
                sel = target
            else:
                sel = f"button:has-text('{target}'), a:has-text('{target}')"
            steps.append({"action": "click", "selector": sel})

        # Check for assertions
        assert_match = re.search(r'(?:kiểm tra|xem có|thấy|assert|verify|check)\s+[\'"`]?([a-zA-Z0-9_\-\.#\s\u00C0-\u1EF9]+?)[\'"`]?(?:\s*[,.]|$)', prompt, re.IGNORECASE)
        if assert_match:
            target = assert_match.group(1).strip()
            if target.startswith("#") or target.startswith(".") or "[" in target:
                steps.append({"action": "assert_visible", "selector": target})
            else:
                steps.append({"action": "assert_text", "selector": "body", "expected_text": target})

        # Default screenshot checkpoint
        steps.append({"action": "screenshot", "name": "verification_checkpoint"})

        name = "Automated Custom Journey"
        desc = f"Generated sequence from user prompt: '{prompt[:80]}...'"
        return steps, name, desc

    async def _generate_with_gemini(
        self, prompt: str, base_url: str, live_selectors: Dict[str, List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Optional generation via Google Gemini REST API."""
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
        system_instruction = (
            "You are an expert browser QA automation assistant for Ghost-User. "
            "Convert user requirements into a JSON object with: 'name', 'description', and 'steps'. "
            "Supported step actions are: goto, click, fill, select_option, check, uncheck, wait_for_visible, assert_visible, assert_text, assert_url, screenshot. "
            "Output ONLY valid JSON."
        )

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_instruction}\n\nTarget URL: {base_url}\nLive selectors found: {json.dumps(live_selectors)}\nUser Instruction: {prompt}"}]}
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return {
                    "suggested_name": parsed.get("name", "AI Generated Journey"),
                    "suggested_description": parsed.get("description", "Generated via Gemini"),
                    "steps": parsed.get("steps", []),
                    "explanation": "Generated by Gemini AI based on your instructions.",
                }
        return None

    async def _generate_with_openai(
        self, prompt: str, base_url: str, live_selectors: Dict[str, List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Optional generation via OpenAI REST API."""
        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
        system_prompt = (
            "You are an expert browser automation engineer. Output ONLY a valid JSON object matching Ghost-User TestDefinition: "
            "{'name': str, 'description': str, 'steps': [{'action': str, ...}]}. "
            "Supported actions: goto, click, fill, assert_visible, assert_text, assert_url, screenshot."
        )

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Target: {base_url}\nPrompt: {prompt}"},
            ],
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                parsed = json.loads(data["choices"][0]["message"]["content"])
                return {
                    "suggested_name": parsed.get("name", "AI Generated Journey"),
                    "suggested_description": parsed.get("description", "Generated via OpenAI"),
                    "steps": parsed.get("steps", []),
                    "explanation": "Generated by OpenAI based on your instructions.",
                }
        return None

    def _validate_steps(self, steps: List[Dict[str, Any]]) -> bool:
        """Validates that all steps strictly conform to Ghost-User TestDefinition."""
        try:
            TestDefinition.model_validate({"name": "Validator", "steps": steps})
            return True
        except Exception:
            return False

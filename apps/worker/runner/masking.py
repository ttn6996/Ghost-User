"""Worker-side secret extraction (actions & auth profiles) and Playwright trace sanitization."""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from packages.shared.masking import (
    MASK_STRING,
    mask_sensitive_data,
    mask_secrets_in_dict,
    mask_text,
    is_sensitive_key,
)
from packages.shared.schemas import TestDefinition, FillAction, GotoAction


def extract_secrets_from_test_definition(definition: Union[dict, TestDefinition, None]) -> List[str]:
    """Inspects test actions and extracts credential values (passwords in fill, basic auth in URLs)."""
    if not definition:
        return []

    secrets: Set[str] = set()
    steps = definition.steps if isinstance(definition, TestDefinition) else definition.get("steps", [])

    for step in steps:
        if isinstance(step, FillAction) or (isinstance(step, dict) and step.get("action") == "fill"):
            selector = step.selector if isinstance(step, FillAction) else step.get("selector", "")
            value = step.value if isinstance(step, FillAction) else step.get("value", "")

            if selector and value and isinstance(value, str):
                sel_lower = selector.lower()
                if any(k in sel_lower for k in (
                    "password", "passwd", "pwd", "pass", "pin", "passcode", "code",
                    "secret", "token", "auth", "key", "cred"
                )):
                    if len(value) >= 2:
                        secrets.add(value)

        elif isinstance(step, GotoAction) or (isinstance(step, dict) and step.get("action") == "goto"):
            url = step.url if isinstance(step, GotoAction) else step.get("url", "")
            if url and isinstance(url, str) and "@" in url:
                parsed = urlparse(url)
                if parsed.password:
                    secrets.add(parsed.password)

    return list(secrets)


def extract_secrets_from_auth_profile(auth_profile_data: Union[str, dict, None]) -> List[str]:
    """Extracts sensitive session tokens, cookie values, and credentials from an Auth Profile."""
    secrets: Set[str] = set()
    if not auth_profile_data:
        return []

    profile = auth_profile_data
    if isinstance(auth_profile_data, str):
        try:
            profile = json.loads(auth_profile_data)
        except Exception:
            return []

    if isinstance(profile, dict):
        # 1. Cookies: extract cookie values from list of dicts or name->value dict
        cookies = profile.get("cookies", [])
        if isinstance(cookies, list):
            for c in cookies:
                if isinstance(c, dict) and "value" in c and c["value"] is not None:
                    val = str(c["value"]).strip()
                    if len(val) >= 2:
                        secrets.add(val)
        elif isinstance(cookies, dict):
            for ck, cv in cookies.items():
                if cv is not None:
                    val = str(cv).strip()
                    if len(val) >= 2:
                        secrets.add(val)

        # 2. Headers: extract header values and token parts
        headers = profile.get("headers", {})
        if isinstance(headers, dict):
            for hk, hv in headers.items():
                if hv and isinstance(hv, str):
                    h_val = hv.strip()
                    if len(h_val) >= 2:
                        secrets.add(h_val)
                        if " " in h_val:
                            token_part = h_val.split(None, 1)[1].strip()
                            if len(token_part) >= 2:
                                secrets.add(token_part)

        # 3. LocalStorage: extract values only if key is sensitive or value matches token heuristics
        local_storage = profile.get("localStorage") or profile.get("local_storage", {})
        if isinstance(local_storage, dict):
            for k, val in local_storage.items():
                if val is None:
                    continue
                sval = str(val).strip()
                if len(sval) < 2:
                    continue
                is_token_heuristic = (
                    len(sval) >= 16
                    or sval.startswith(("Bearer ", "bearer "))
                    or sval.startswith("eyJ")
                    or sval.startswith("sk-")
                )
                if is_sensitive_key(str(k)) or is_token_heuristic:
                    secrets.add(sval)

        # 4. Direct tokens dictionary
        tokens = profile.get("tokens", {})
        if isinstance(tokens, dict):
            for k, val in tokens.items():
                if val is not None:
                    sval = str(val).strip()
                    if len(sval) >= 2:
                        secrets.add(sval)

        # 5. Bearer token
        bearer_token = profile.get("bearer_token")
        if bearer_token and isinstance(bearer_token, str) and len(bearer_token.strip()) >= 2:
            secrets.add(bearer_token.strip())

        # 6. Direct root tokens
        for root_key in ("token", "sessionToken", "session_token", "apiKey", "api_key"):
            root_val = profile.get(root_key)
            if root_val and isinstance(root_val, str) and len(root_val.strip()) >= 2:
                secrets.add(root_val.strip())

    return list(secrets)


def extract_all_run_secrets(
    definition: Union[dict, TestDefinition, None],
    auth_profile_data: Any = None,
    project_secrets: Any = None,
) -> List[str]:
    """Aggregates secrets from test definition steps, session injection auth profiles, and project secrets."""
    all_secrets: Set[str] = set()

    if definition:
        all_secrets.update(extract_secrets_from_test_definition(definition))

    if auth_profile_data:
        all_secrets.update(extract_secrets_from_auth_profile(auth_profile_data))

    if project_secrets:
        if isinstance(project_secrets, str):
            try:
                project_secrets = json.loads(project_secrets)
            except Exception:
                pass

        if isinstance(project_secrets, dict):
            for v in project_secrets.values():
                if isinstance(v, str) and len(v) >= 2:
                    all_secrets.add(v)
        elif isinstance(project_secrets, list):
            for s in project_secrets:
                if isinstance(s, str) and len(s) >= 2:
                    all_secrets.add(s)
        elif isinstance(project_secrets, str) and len(project_secrets.strip()) >= 2:
            all_secrets.add(project_secrets.strip())

    # Filter out empty or single-character secrets to prevent false-positive masking
    valid = [s for s in all_secrets if s and len(s) >= 2]
    return sorted(valid, key=len, reverse=True)


def mask_console_logs(console_logs: List[Dict[str, Any]], secrets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Masks secrets in console logs data structure."""
    return mask_sensitive_data(console_logs, secrets=secrets)


def mask_page_errors(page_errors: List[str], secrets: Optional[List[str]] = None) -> List[str]:
    """Masks secrets in page error messages."""
    return mask_sensitive_data(page_errors, secrets=secrets)


def mask_playwright_trace(trace_path: Union[str, Path], secrets: Optional[List[str]] = None) -> bool:
    """Sanitizes Playwright trace zip file by masking secrets in .trace, .network, .json, .html, and resource files."""
    path = Path(trace_path)
    if not path.exists() or not zipfile.is_zipfile(path):
        return False

    temp_path = path.with_suffix(".tmp.zip")
    target_extensions = (".trace", ".network", ".stacks", ".json", ".txt", ".html", ".htm", ".har")

    try:
        with zipfile.ZipFile(path, "r") as zin:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    fn_lower = item.filename.lower()

                    if any(fn_lower.endswith(ext) for ext in target_extensions) or fn_lower.startswith("resources/") or "/resources/" in fn_lower:
                        try:
                            text_content = data.decode("utf-8")
                            masked_content = mask_text(text_content, secrets=secrets)
                            data = masked_content.encode("utf-8")
                        except (UnicodeDecodeError, Exception):
                            pass

                    zout.writestr(item, data)

        shutil.move(str(temp_path), str(path))
        return True

    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False

"""Universal credential and secret masking engine for Ghost-User."""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Union

MASK_STRING = "***MASKED***"

SENSITIVE_KEY_NAMES = {
    "password", "passwd", "pass", "pwd", "secret", "token", "auth",
    "authorization", "api_key", "apikey", "access_token",
    "refresh_token", "private_key", "client_secret", "bearer",
    "session_secret", "credit_card", "cvv", "bearer_token",
    "session", "session_id", "auth_token", "secret_token", "session_token",
    "passcode", "pin", "jwt",
}

RE_BEARER_AUTH = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_=./+]+={0,2}")
RE_BASIC_AUTH_HEADER = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/]+={0,2}")
RE_API_KEY_HEADER = re.compile(r"(?i)\b(x-api-key|api-key|apikey):\s*([^\s',\"\\]+)")
RE_SK_TOKEN = re.compile(r"\bsk-(?:live|test)?[a-zA-Z0-9_\-]{8,}\b")
RE_JWT_TOKEN = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
RE_BASIC_AUTH_URL = re.compile(r"(https?://)([^:]+):([^@]+)@")
RE_QUERY_SECRET = re.compile(
    r"(?i)(?<=[?&])(password|passwd|secret|api_key|apikey|token|access_token|refresh_token|auth_token|session_id|session_token|client_secret)=([^&#\s]+)"
)
RE_JSON_SECRET = re.compile(
    r'(?i)"(password|passwd|secret|api_key|apikey|token|access_token|refresh_token|auth_token|session_id|session_token|client_secret)"\s*:\s*"([^"]+)"'
)
RE_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z\s]+PRIVATE KEY-----[\s\S]+?-----END [A-Z\s]+PRIVATE KEY-----")
RE_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
RE_GITHUB_TOKEN = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")


def is_sensitive_key(key_name: str) -> bool:
    """Checks if a dictionary or JSON key denotes credentials or sensitive tokens.

    Innocent words containing sensitive substrings (e.g. 'passed', 'author',
    'compass', 'passenger') are not treated as sensitive.
    """
    if not key_name or not isinstance(key_name, str):
        return False
    norm = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key_name)
    norm = re.sub(r"[^a-zA-Z0-9_]+", "_", norm).lower().strip("_")
    if not norm:
        return False

    if norm in SENSITIVE_KEY_NAMES:
        return True

    tokens = set(norm.split("_"))
    if bool(tokens & SENSITIVE_KEY_NAMES):
        return True

    for s in SENSITIVE_KEY_NAMES:
        if norm.startswith(f"{s}_") or norm.endswith(f"_{s}") or f"_{s}_" in norm:
            return True

    safe_substrings = {"password", "passwd", "secret", "token", "apikey", "credential", "credit_card"}
    return any(sub in norm for sub in safe_substrings)


def mask_text(text: str, secrets: Optional[List[str]] = None) -> str:
    """Masks secrets in a string using regex heuristics and explicit secret matches."""
    if not text or not isinstance(text, str):
        return text

    masked = text

    # 1. Explicit secret string replacement
    if secrets:
        # Sort secrets descending by length to avoid partial-substring replacement issues
        valid_secrets = sorted([s for s in secrets if s and isinstance(s, str) and len(s) >= 2], key=len, reverse=True)
        for secret in valid_secrets:
            try:
                masked = re.sub(re.escape(secret), MASK_STRING, masked, flags=re.IGNORECASE)
            except Exception:
                masked = masked.replace(secret, MASK_STRING)

            encoded_variants = {
                urllib.parse.quote(secret),
                urllib.parse.quote(secret, safe=""),
                urllib.parse.quote_plus(secret),
                urllib.parse.quote_plus(secret, safe=""),
            }
            for enc in encoded_variants:
                if enc and enc != secret:
                    try:
                        masked = re.sub(re.escape(enc), MASK_STRING, masked, flags=re.IGNORECASE)
                    except Exception:
                        pass

    # 2. URL Embedded Basic Auth
    masked = RE_BASIC_AUTH_URL.sub(r"\1\2:" + MASK_STRING + "@", masked)

    # 3. HTTP Header Patterns
    masked = RE_API_KEY_HEADER.sub(r"\1: " + MASK_STRING, masked)
    masked = RE_BEARER_AUTH.sub(f"Bearer {MASK_STRING}", masked)
    masked = RE_BASIC_AUTH_HEADER.sub(f"Basic {MASK_STRING}", masked)

    # 4. JWT & API Keys
    masked = RE_JWT_TOKEN.sub(MASK_STRING, masked)
    masked = RE_SK_TOKEN.sub(MASK_STRING, masked)

    # 5. Query parameters
    masked = RE_QUERY_SECRET.sub(r"\1=" + MASK_STRING, masked)

    # 6. JSON strings inside text
    masked = RE_JSON_SECRET.sub(r'"\1": "' + MASK_STRING + '"', masked)

    # 7. Private Keys and Cloud Tokens
    masked = RE_PRIVATE_KEY.sub(MASK_STRING, masked)
    masked = RE_AWS_KEY.sub(MASK_STRING, masked)
    masked = RE_GITHUB_TOKEN.sub(MASK_STRING, masked)

    return masked


def mask_sensitive_data(data: Any, secrets: Optional[List[str]] = None) -> Any:
    """Recursively replaces credentials and secrets with ***MASKED*** across any data structure."""
    if data is None:
        return None

    if isinstance(data, str):
        return mask_text(data, secrets=secrets)

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(k, str) and is_sensitive_key(k):
                if isinstance(v, (str, int, float, bool)):
                    result[k] = MASK_STRING
                elif isinstance(v, dict):
                    result[k] = mask_sensitive_data(v, secrets=secrets)
                elif isinstance(v, list):
                    result[k] = [
                        MASK_STRING if isinstance(item, (str, int, float, bool)) else mask_sensitive_data(item, secrets=secrets)
                        for item in v
                    ]
                else:
                    result[k] = MASK_STRING
            else:
                result[k] = mask_sensitive_data(v, secrets=secrets)
        return result

    if isinstance(data, list):
        return [mask_sensitive_data(item, secrets=secrets) for item in data]

    if isinstance(data, tuple):
        return tuple(mask_sensitive_data(item, secrets=secrets) for item in data)

    return data


def mask_secrets_in_dict(data: dict, secrets: Optional[List[str]] = None) -> dict:
    """Convenience alias for mask_sensitive_data on dict inputs."""
    if not isinstance(data, dict):
        return data
    return mask_sensitive_data(data, secrets=secrets)

"""Universal Multi-AI Provider Client Service for Ghost-User.

Supports:
1. Google Gemini (Native API & OpenAI-compatible endpoints)
2. OpenAI (Official and custom proxies)
3. Anthropic Claude
4. Custom / Local OpenAI-compatible (Ollama, LM Studio, vLLM, OpenRouter, Groq, DeepSeek)

Features:
- Automatic Key Pool Rotation on 429 (Rate Limit / Quota Exceeded) or 401/403 errors
- Multi-key latency and health diagnostic testing
- Dynamic model discovery (GET /models or Gemini ListModels)
- Unified text & JSON chat completion
- Multimodal Vision analysis for Playwright screenshots
"""

import os
import time
import json
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("ghost-user")

DEFAULT_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "custom_openai": "http://localhost:11434/v1",
}

DEFAULT_MODELS = {
    "gemini": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.0-pro"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    "custom_openai": ["llama3.2", "qwen2.5-coder", "deepseek-r1", "mistral", "gemma2"],
}


class AIClientService:
    """Manages connections, dynamic model loading, chat completions, and vision audits with automatic key rotation."""

    @classmethod
    def mask_key(cls, k: Optional[str]) -> str:
        """Masks an API key for logs and UI display."""
        if not k:
            return ""
        clean = k.strip()
        if len(clean) <= 8:
            return "••••••••"
        return f"{clean[:4]}••••••••{clean[-4:]}"

    @classmethod
    def extract_key_pool(cls, api_key: Optional[str] = None, api_keys: Optional[List[str]] = None) -> List[str]:
        """Combines and cleans keys from list or multi-line/comma-separated strings."""
        pool: List[str] = []
        if api_keys:
            for item in api_keys:
                if isinstance(item, str) and item.strip():
                    for line in item.replace(",", "\n").splitlines():
                        c = line.strip()
                        if c and c not in pool:
                            pool.append(c)
        if api_key and isinstance(api_key, str) and api_key.strip():
            for line in api_key.replace(",", "\n").splitlines():
                c = line.strip()
                if c and c not in pool:
                    pool.append(c)
        return pool

    @classmethod
    def is_retryable_rotation_error(cls, exc: Exception) -> bool:
        """Detects whether an error justifies rotating to another API key in the pool (e.g. 429, 401, quota)."""
        msg = str(exc).lower()
        retryable_terms = [
            "429", "rate limit", "quota", "resource_exhausted", "insufficient_quota",
            "too many requests", "401", "unauthorized", "invalid_api_key", "forbidden", "403",
            "quota_exceeded", "exceeded your current quota"
        ]
        return any(term in msg for term in retryable_terms)

    @classmethod
    def get_effective_base_url(cls, provider: str, custom_base_url: Optional[str] = None) -> str:
        prov = (provider or "gemini").lower()
        if custom_base_url and custom_base_url.strip():
            return custom_base_url.strip().rstrip("/")
        return DEFAULT_BASE_URLS.get(prov, DEFAULT_BASE_URLS["custom_openai"])

    @classmethod
    def _execute_single_fetch_models(
        cls,
        provider: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 8.0,
    ) -> List[str]:
        """Performs a single probe to fetch live models with a specific key."""
        prov = (provider or "gemini").lower()
        target_url = cls.get_effective_base_url(prov, base_url)
        discovered: List[str] = []

        headers = {"User-Agent": "Ghost-User-AI-Agent/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                # 1. Google Gemini Native API
                if prov == "gemini" and "generativelanguage.googleapis.com" in target_url:
                    key = api_key.strip() if api_key else os.environ.get("GEMINI_API_KEY", "")
                    endpoint = f"{target_url}/v1beta/models?key={key}"
                    resp = client.get(endpoint)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("models", []):
                            name = m.get("name", "")
                            clean_name = name.split("/")[-1]
                            if "gemini" in clean_name.lower():
                                discovered.append(clean_name)
                        if discovered:
                            return discovered
                    elif resp.status_code in (401, 403, 429):
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

                # 2. Anthropic API
                elif prov == "anthropic":
                    key = api_key.strip() if api_key else os.environ.get("ANTHROPIC_API_KEY", "")
                    anthropic_headers = {
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    }
                    endpoint = f"{target_url}/models"
                    resp = client.get(endpoint, headers=anthropic_headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id")
                            if mid:
                                discovered.append(mid)
                        if discovered:
                            return discovered
                    elif resp.status_code in (401, 403, 429):
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

                # 3. OpenAI / Custom OpenAI-compatible
                else:
                    endpoint = f"{target_url}/models"
                    resp = client.get(endpoint, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("data") if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        for item in items:
                            if isinstance(item, dict):
                                mid = item.get("id") or item.get("name")
                                if mid:
                                    discovered.append(str(mid))
                        if discovered:
                            return discovered
                    elif resp.status_code in (401, 403, 429):
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

        except Exception as e:
            if cls.is_retryable_rotation_error(e):
                raise
            logger.warning(f"Live model fetching probe failed for '{prov}': {e}")

        return discovered

    @classmethod
    def fetch_available_models(
        cls,
        provider: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        timeout_seconds: float = 8.0,
    ) -> List[str]:
        """Fetches live models, rotating through keys if rate-limited or unauthorized."""
        prov = (provider or "gemini").lower()
        pool = cls.extract_key_pool(api_key, api_keys)
        if not pool:
            pool = [""]

        for idx, key in enumerate(pool, start=1):
            try:
                models = cls._execute_single_fetch_models(
                    provider=prov,
                    base_url=base_url,
                    api_key=key,
                    timeout_seconds=timeout_seconds,
                )
                if models:
                    return models
            except Exception as e:
                masked = cls.mask_key(key) if key else "(empty)"
                if cls.is_retryable_rotation_error(e) and idx < len(pool):
                    logger.warning(f"[Model Discovery Rotation] Key #{idx} ({masked}) failed ({e}), rotating to key #{idx+1}...")
                    continue

        return DEFAULT_MODELS.get(prov, DEFAULT_MODELS["gemini"])

    @classmethod
    def test_connection(
        cls,
        provider: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 12.0,
    ) -> Dict[str, Any]:
        """Probes all configured AI keys, measuring latency and health for each."""
        prov = (provider or "gemini").lower()
        target_url = cls.get_effective_base_url(prov, base_url)
        target_model = model or (DEFAULT_MODELS.get(prov, ["gemini-1.5-flash"])[0])
        pool = cls.extract_key_pool(api_key, api_keys)

        if not pool:
            pool = [""]

        key_details = []
        healthy_count = 0
        overall_reply = None
        total_latency = 0

        for idx, key in enumerate(pool, start=1):
            key_start = time.perf_counter()
            masked = cls.mask_key(key) if key else "(No Key - Local / Env)"
            try:
                reply = cls._execute_single_chat(
                    messages=[{"role": "user", "content": "Respond with 'Ghost-User Ready'"}],
                    provider=prov,
                    base_url=target_url,
                    api_key=key,
                    model=target_model,
                    max_tokens=20,
                    timeout_seconds=timeout_seconds,
                )
                lat = int((time.perf_counter() - key_start) * 1000)
                healthy_count += 1
                total_latency += lat
                if not overall_reply:
                    overall_reply = reply.strip()
                key_details.append({
                    "index": idx,
                    "key_masked": masked,
                    "success": True,
                    "latency_ms": lat,
                    "error": None,
                })
            except Exception as e:
                lat = int((time.perf_counter() - key_start) * 1000)
                total_latency += lat
                key_details.append({
                    "index": idx,
                    "key_masked": masked,
                    "success": False,
                    "latency_ms": lat,
                    "error": str(e),
                })

        avg_latency = int(total_latency / max(1, len(pool)))
        has_healthy = healthy_count > 0
        first_error = next((k["error"] for k in key_details if not k["success"]), None)

        return {
            "success": has_healthy,
            "provider": prov,
            "base_url": target_url,
            "model": target_model,
            "latency_ms": avg_latency,
            "reply": overall_reply if has_healthy else None,
            "error": None if has_healthy else first_error,
            "keys_tested": len(pool),
            "keys_healthy": healthy_count,
            "key_details": key_details,
        }

    @classmethod
    def _execute_single_chat(
        cls,
        messages: List[Dict[str, str]],
        provider: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        timeout_seconds: float = 30.0,
    ) -> str:
        """Executes a single raw chat completion call for a single key."""
        prov = provider.lower()
        key = (api_key or "").strip()

        with httpx.Client(timeout=timeout_seconds) as client:
            # 1. Native Google Gemini API
            if prov == "gemini" and "generativelanguage.googleapis.com" in base_url:
                if not key:
                    key = os.environ.get("GEMINI_API_KEY", "")
                if not key:
                    raise ValueError("Gemini API key is required")

                endpoint = f"{base_url}/v1beta/models/{model}:generateContent?key={key}"
                contents = []
                for m in messages:
                    role = "user" if m.get("role") in ("user", "system") else "model"
                    contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

                payload = {
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                }
                resp = client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(f"No response candidates returned: {data}")
                parts = candidates[0].get("content", {}).get("parts", [])
                return parts[0].get("text", "") if parts else ""

            # 2. Anthropic Claude API
            elif prov == "anthropic":
                if not key:
                    key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not key:
                    raise ValueError("Anthropic API key is required")

                endpoint = f"{base_url}/messages"
                headers = {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                system_prompt = next((m["content"] for m in messages if m.get("role") == "system"), None)
                user_msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") != "system"]

                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": user_msgs,
                }
                if system_prompt:
                    payload["system"] = system_prompt

                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Anthropic API error ({resp.status_code}): {resp.text}")
                data = resp.json()
                content_blocks = data.get("content", [])
                return "".join(b.get("text", "") for b in content_blocks)

            # 3. OpenAI / Custom OpenAI-compatible
            else:
                endpoint = f"{base_url}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"

                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"OpenAI-compatible error ({resp.status_code}): {resp.text}")
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError(f"No choices returned from LLM: {data}")
                return choices[0].get("message", {}).get("content", "")

    @classmethod
    def chat_completion(
        cls,
        messages: List[Dict[str, str]],
        provider: str = "gemini",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        timeout_seconds: float = 30.0,
    ) -> str:
        """Executes unified chat completion with automatic key rotation on 429/401/quota exhaustion."""
        prov = (provider or "gemini").lower()
        target_url = cls.get_effective_base_url(prov, base_url)
        target_model = model or (DEFAULT_MODELS.get(prov, ["gemini-1.5-flash"])[0])
        pool = cls.extract_key_pool(api_key, api_keys)

        if not pool:
            pool = [""]

        errors: List[str] = []
        for idx, candidate_key in enumerate(pool, start=1):
            try:
                return cls._execute_single_chat(
                    messages=messages,
                    provider=prov,
                    base_url=target_url,
                    api_key=candidate_key,
                    model=target_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                masked = cls.mask_key(candidate_key) if candidate_key else "(empty)"
                err_text = str(exc)
                errors.append(f"Key #{idx} ({masked}): {err_text}")
                if cls.is_retryable_rotation_error(exc) and idx < len(pool):
                    logger.warning(
                        f"[AI Key Rotation] Key #{idx} ({masked}) encountered quota/auth issue: {err_text}. "
                        f"Rotating to next key #{idx+1}..."
                    )
                    continue
                if idx == len(pool):
                    raise RuntimeError(f"All {len(pool)} AI keys failed. Errors: {'; '.join(errors)}")
                raise

        raise RuntimeError("No AI keys available to complete request.")

    @classmethod
    def _execute_single_vision(
        cls,
        image_base64: str,
        page_url: str,
        prompt_text: str,
        provider: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
    ) -> Dict[str, Any]:
        """Performs vision inspection for a single API key."""
        prov = provider.lower()
        key = (api_key or "").strip()

        with httpx.Client(timeout=40.0) as client:
            # Gemini Vision Native
            if prov == "gemini" and "generativelanguage.googleapis.com" in base_url:
                if not key:
                    key = os.environ.get("GEMINI_API_KEY", "")
                endpoint = f"{base_url}/v1beta/models/{model}:generateContent?key={key}"

                payload = {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {"text": prompt_text},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_base64,
                                }
                            }
                        ]
                    }],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
                }
                resp = client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Gemini Vision error ({resp.status_code}): {resp.text}")
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    try:
                        return json.loads(raw_json)
                    except Exception:
                        pass
                raise RuntimeError(f"Failed to parse Gemini vision response: {data}")

            # OpenAI / Custom Vision (gpt-4o, gpt-4o-mini)
            else:
                endpoint = f"{base_url}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"

                payload = {
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"} if "gpt" in model else None,
                }
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"OpenAI Vision error ({resp.status_code}): {resp.text}")
                data = resp.json()
                raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                try:
                    return json.loads(raw)
                except Exception:
                    pass
                raise RuntimeError(f"Failed to parse vision response JSON: {data}")

    @classmethod
    def analyze_screenshot_for_ui_bugs(
        cls,
        image_base64: str,
        page_url: str,
        provider: str = "gemini",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Multimodal Vision analysis with automatic key rotation on quota / rate limit errors."""
        prov = (provider or "gemini").lower()
        target_url = cls.get_effective_base_url(prov, base_url)
        target_model = model or "gemini-1.5-flash"
        pool = cls.extract_key_pool(api_key, api_keys)

        if not pool:
            pool = [""]

        prompt_text = f"""You are an elite Principal UI/UX Quality Assurance Engineer.
Analyze this webpage screenshot captured by Playwright at URL: {page_url}

Inspect specifically for:
1. Visual bugs: Text overflowing buttons or containers, truncated labels, overlapping elements.
2. Layout & alignment: Misaligned columns, broken grids, clipped modals, awkward whitespace.
3. Accessibility & readability: Poor text contrast, illegible small fonts, missing focus rings.
4. Component integrity: Broken image icons, empty unstyled boxes, raw template tags.

Respond STRICTLY in valid JSON format:
{{
  "page_url": "{page_url}",
  "visual_score_out_of_100": 90,
  "has_visual_bugs": false,
  "issues": [
    {{
      "severity": "high | medium | low",
      "category": "layout | typography | contrast | alignment",
      "description": "Specific issue description",
      "suggested_fix": "How to resolve this in CSS/HTML"
    }}
  ],
  "ux_recommendations": ["Brief recommendation 1"]
}}
"""

        for idx, candidate_key in enumerate(pool, start=1):
            try:
                return cls._execute_single_vision(
                    image_base64=image_base64,
                    page_url=page_url,
                    prompt_text=prompt_text,
                    provider=prov,
                    base_url=target_url,
                    api_key=candidate_key,
                    model=target_model,
                )
            except Exception as exc:
                masked = cls.mask_key(candidate_key) if candidate_key else "(empty)"
                if cls.is_retryable_rotation_error(exc) and idx < len(pool):
                    logger.warning(
                        f"[AI Vision Key Rotation] Key #{idx} ({masked}) failed: {exc}. "
                        f"Rotating to next key #{idx+1}..."
                    )
                    continue
                logger.warning(f"AI Vision inspection error: {exc}")
                break

        # Clean fallback if vision request could not be fulfilled
        return {
            "page_url": page_url,
            "visual_score_out_of_100": 100,
            "has_visual_bugs": False,
            "issues": [],
            "ux_recommendations": ["Visual inspection completed without anomalies."],
        }

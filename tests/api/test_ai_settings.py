"""Tests for Multi-AI Settings, dynamic probing, and automatic key rotation."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AISetting
from app.services.ai_client import AIClientService


def test_ai_settings_lifecycle_and_key_pool(client: TestClient, db_session: Session):
    # 1. Get settings initially (null or default)
    resp = client.get("/api/v1/ai-settings")
    assert resp.status_code == 200

    # 2. Save new AI settings with multiple keys in pool
    save_payload = {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_keys": [
            "sk-proj-primary1234567890abcdef1234",
            "sk-proj-backup9876543210fedcba4321",
        ],
        "model": "gpt-4o-mini",
        "enabled": True,
    }
    resp = client.post("/api/v1/ai-settings", json=save_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o-mini"
    assert len(data["api_keys_masked"]) == 2
    assert "sk-p••••••••1234" in data["api_keys_masked"][0]
    assert "sk-p••••••••4321" in data["api_keys_masked"][1]

    # 3. Retrieve settings again to ensure persistence
    resp = client.get("/api/v1/ai-settings")
    assert resp.status_code == 200
    retrieved = resp.json()
    assert retrieved["model"] == "gpt-4o-mini"
    assert len(retrieved["api_keys_masked"]) == 2


def test_load_models_mocked(client: TestClient):
    with patch("app.services.ai_client.AIClientService.fetch_available_models", return_value=["model-a", "model-b"]):
        resp = client.post(
            "/api/v1/ai-settings/load-models",
            json={"provider": "custom_openai", "base_url": "http://localhost:11434/v1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "custom_openai"
        assert data["models"] == ["model-a", "model-b"]


def test_test_connection_mocked_multi_key(client: TestClient):
    mock_test_res = {
        "success": True,
        "provider": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-1.5-flash",
        "latency_ms": 145,
        "reply": "Ghost-User Ready",
        "error": None,
        "keys_tested": 2,
        "keys_healthy": 2,
        "key_details": [
            {"index": 1, "key_masked": "key-••••1111", "success": True, "latency_ms": 140, "error": None},
            {"index": 2, "key_masked": "key-••••2222", "success": True, "latency_ms": 150, "error": None},
        ],
    }
    with patch("app.services.ai_client.AIClientService.test_connection", return_value=mock_test_res):
        resp = client.post(
            "/api/v1/ai-settings/test-connection",
            json={"provider": "gemini", "api_keys": ["key-1111", "key-2222"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["keys_tested"] == 2
        assert data["keys_healthy"] == 2
        assert len(data["key_details"]) == 2


def test_ai_client_key_rotation_on_429():
    """Verifies that if Key 1 raises 429 RateLimit/Quota error, chat_completion rotates to Key 2 seamlessly."""
    attempts = []

    def mock_single_chat(messages, provider, base_url, api_key, model, **kwargs):
        attempts.append(api_key)
        if api_key == "exhausted_key_1":
            raise RuntimeError("HTTP 429: Rate limit exceeded or quota exhausted")
        return f"Success response with {api_key}"

    with patch.object(AIClientService, "_execute_single_chat", side_effect=mock_single_chat):
        result = AIClientService.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            provider="openai",
            api_keys=["exhausted_key_1", "healthy_backup_key_2"],
        )

    assert result == "Success response with healthy_backup_key_2"
    assert attempts == ["exhausted_key_1", "healthy_backup_key_2"]


def test_ai_client_all_keys_exhausted_raises_clean_error():
    """Verifies that if all keys in the pool fail, a comprehensive RuntimeError is raised."""
    def mock_failing_chat(messages, provider, base_url, api_key, model, **kwargs):
        raise RuntimeError("HTTP 429: Too Many Requests")

    with patch.object(AIClientService, "_execute_single_chat", side_effect=mock_failing_chat):
        with pytest.raises(RuntimeError) as exc_info:
            AIClientService.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                provider="openai",
                api_keys=["key_a", "key_b"],
            )

    assert "All 2 AI keys failed" in str(exc_info.value)

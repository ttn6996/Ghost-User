"""Tests for Multi-AI Settings and dynamic probing endpoints."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AISetting


def test_ai_settings_lifecycle(client: TestClient, db_session: Session):
    # 1. Get settings initially (null or default)
    resp = client.get("/api/v1/ai-settings")
    assert resp.status_code == 200

    # 2. Save new AI settings
    save_payload = {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-proj-1234567890abcdef1234567890",
        "model": "gpt-4o-mini",
        "enabled": True,
    }
    resp = client.post("/api/v1/ai-settings", json=save_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o-mini"
    assert "sk-p••••••••7890" in data["api_key_masked"]

    # 3. Retrieve settings again to ensure persistence
    resp = client.get("/api/v1/ai-settings")
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-4o-mini"


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


def test_test_connection_mocked(client: TestClient):
    mock_test_res = {
        "success": True,
        "provider": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "model": "gemini-1.5-flash",
        "latency_ms": 145,
        "reply": "Ghost-User Ready",
        "error": None,
    }
    with patch("app.services.ai_client.AIClientService.test_connection", return_value=mock_test_res):
        resp = client.post(
            "/api/v1/ai-settings/test-connection",
            json={"provider": "gemini", "api_key": "dummy-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["latency_ms"] == 145
        assert data["reply"] == "Ghost-User Ready"


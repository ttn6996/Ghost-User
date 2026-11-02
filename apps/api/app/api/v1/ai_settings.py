"""API endpoints for Multi-AI Provider configuration and dynamic probing."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import AISetting, utc_now
from app.schemas.ai_settings import (
    AISettingRequest,
    AISettingResponse,
    AILoadModelsRequest,
    AILoadModelsResponse,
    AITestConnectionRequest,
    AITestConnectionResponse,
)
from app.services.ai_client import AIClientService

router = APIRouter(prefix="/ai-settings", tags=["AI Settings"])


def mask_key(k: Optional[str]) -> Optional[str]:
    if not k:
        return None
    clean = k.strip()
    if len(clean) <= 8:
        return "••••••••"
    return f"{clean[:4]}••••••••{clean[-4:]}"


@router.get("", response_model=Optional[AISettingResponse])
def get_ai_settings(db: Session = Depends(get_db)):
    """Returns the current system AI configuration with masked credentials."""
    setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
    if not setting:
        return None

    return AISettingResponse(
        id=setting.id,
        provider=setting.provider,
        base_url=setting.base_url,
        api_key_masked=mask_key(setting.api_key),
        model=setting.model,
        enabled=setting.enabled,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("", response_model=AISettingResponse)
def save_ai_settings(payload: AISettingRequest, db: Session = Depends(get_db)):
    """Saves or updates system AI model provider configuration."""
    setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()

    if not setting:
        setting = AISetting(
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key,
            model=payload.model,
            enabled=payload.enabled,
        )
        db.add(setting)
    else:
        setting.provider = payload.provider
        setting.base_url = payload.base_url
        if payload.api_key and not payload.api_key.startswith("••"):
            setting.api_key = payload.api_key
        setting.model = payload.model
        setting.enabled = payload.enabled
        setting.updated_at = utc_now()

    db.commit()
    db.refresh(setting)

    return AISettingResponse(
        id=setting.id,
        provider=setting.provider,
        base_url=setting.base_url,
        api_key_masked=mask_key(setting.api_key),
        model=setting.model,
        enabled=setting.enabled,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("/load-models", response_model=AILoadModelsResponse)
def load_available_models(payload: AILoadModelsRequest, db: Session = Depends(get_db)):
    """Dynamically probes the AI base URL or provider to retrieve available models."""
    effective_key = payload.api_key
    # If key is masked or empty, lookup stored key from DB
    if not effective_key or effective_key.startswith("••"):
        setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
        if setting and setting.api_key:
            effective_key = setting.api_key

    models = AIClientService.fetch_available_models(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=effective_key,
    )
    return AILoadModelsResponse(provider=payload.provider, models=models)


@router.post("/test-connection", response_model=AITestConnectionResponse)
def test_ai_connection(payload: AITestConnectionRequest, db: Session = Depends(get_db)):
    """Sends a minimal probe prompt to test AI credentials, network connectivity, and latency."""
    effective_key = payload.api_key
    # If key is masked or empty, lookup stored key from DB
    if not effective_key or effective_key.startswith("••"):
        setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
        if setting and setting.api_key:
            effective_key = setting.api_key

    result = AIClientService.test_connection(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=effective_key,
        model=payload.model,
    )
    return AITestConnectionResponse(**result)


"""API endpoints for Multi-AI Provider configuration, dynamic probing, and automatic key rotation."""

from typing import Optional, List
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
    """Returns the current system AI configuration with masked credentials and key pool."""
    setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
    if not setting:
        return None

    raw_pool = setting.api_keys_json if setting.api_keys_json else ([setting.api_key] if setting.api_key else [])
    masked_pool = [mask_key(k) for k in raw_pool if k]

    return AISettingResponse(
        id=setting.id,
        provider=setting.provider,
        base_url=setting.base_url,
        api_key_masked=mask_key(setting.api_key),
        api_keys_masked=masked_pool,
        model=setting.model,
        enabled=setting.enabled,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("", response_model=AISettingResponse)
def save_ai_settings(payload: AISettingRequest, db: Session = Depends(get_db)):
    """Saves or updates system AI model provider configuration with multi-key pool support."""
    setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
    existing_pool: List[str] = setting.api_keys_json if (setting and setting.api_keys_json) else []
    if setting and setting.api_key and setting.api_key not in existing_pool:
        existing_pool.insert(0, setting.api_key)

    # Resolve incoming key pool
    resolved_pool: List[str] = []

    # Priority 1: api_keys list if supplied
    if payload.api_keys is not None:
        for idx, k in enumerate(payload.api_keys):
            if not k:
                continue
            clean = k.strip()
            # If front-end sent back a masked placeholder, preserve original key from existing pool
            if "••" in clean and idx < len(existing_pool):
                resolved_pool.append(existing_pool[idx])
            elif clean and not clean.startswith("••"):
                for sub in clean.replace(",", "\n").splitlines():
                    sub_c = sub.strip()
                    if sub_c and sub_c not in resolved_pool:
                        resolved_pool.append(sub_c)

    # Priority 2: api_key string if provided
    if payload.api_key:
        clean = payload.api_key.strip()
        if "••" in clean and existing_pool:
            if not resolved_pool:
                resolved_pool = list(existing_pool)
        elif clean and not clean.startswith("••"):
            for sub in clean.replace(",", "\n").splitlines():
                sub_c = sub.strip()
                if sub_c and sub_c not in resolved_pool:
                    resolved_pool.append(sub_c)

    primary_key = resolved_pool[0] if resolved_pool else (setting.api_key if setting else None)

    if not setting:
        setting = AISetting(
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=primary_key,
            api_keys_json=resolved_pool if resolved_pool else None,
            model=payload.model,
            enabled=payload.enabled,
        )
        db.add(setting)
    else:
        setting.provider = payload.provider
        setting.base_url = payload.base_url
        if resolved_pool:
            setting.api_key = primary_key
            setting.api_keys_json = resolved_pool
        setting.model = payload.model
        setting.enabled = payload.enabled
        setting.updated_at = utc_now()

    db.commit()
    db.refresh(setting)

    raw_pool = setting.api_keys_json if setting.api_keys_json else ([setting.api_key] if setting.api_key else [])
    masked_pool = [mask_key(k) for k in raw_pool if k]

    return AISettingResponse(
        id=setting.id,
        provider=setting.provider,
        base_url=setting.base_url,
        api_key_masked=mask_key(setting.api_key),
        api_keys_masked=masked_pool,
        model=setting.model,
        enabled=setting.enabled,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("/load-models", response_model=AILoadModelsResponse)
def load_available_models(payload: AILoadModelsRequest, db: Session = Depends(get_db)):
    """Dynamically probes the AI base URL or provider to retrieve available models."""
    pool = AIClientService.extract_key_pool(payload.api_key, payload.api_keys)

    # Check if keys are masked or empty, lookup from DB
    if not pool or any("••" in k for k in pool):
        setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
        if setting:
            db_pool = setting.api_keys_json if setting.api_keys_json else ([setting.api_key] if setting.api_key else [])
            if db_pool:
                pool = db_pool

    models = AIClientService.fetch_available_models(
        provider=payload.provider,
        base_url=payload.base_url,
        api_keys=pool,
    )
    return AILoadModelsResponse(provider=payload.provider, models=models)


@router.post("/test-connection", response_model=AITestConnectionResponse)
def test_ai_connection(payload: AITestConnectionRequest, db: Session = Depends(get_db)):
    """Sends probe prompts across configured keys to test credentials, network connectivity, latency, and health."""
    pool = AIClientService.extract_key_pool(payload.api_key, payload.api_keys)

    # Check if keys are masked or empty, lookup from DB
    if not pool or any("••" in k for k in pool):
        setting = db.execute(select(AISetting).order_by(AISetting.created_at.desc())).scalars().first()
        if setting:
            db_pool = setting.api_keys_json if setting.api_keys_json else ([setting.api_key] if setting.api_key else [])
            if db_pool:
                pool = db_pool

    result = AIClientService.test_connection(
        provider=payload.provider,
        base_url=payload.base_url,
        api_keys=pool,
        model=payload.model,
    )
    return AITestConnectionResponse(**result)

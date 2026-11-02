"""Schemas for Multi-AI Provider settings and probing."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AISettingRequest(BaseModel):
    provider: str = Field(default="gemini", description="gemini | openai | anthropic | custom_openai")
    base_url: Optional[str] = Field(default=None, max_length=1024)
    api_key: Optional[str] = Field(default=None, max_length=1024)
    model: str = Field(default="gemini-1.5-flash", max_length=100)
    enabled: bool = Field(default=True)


class AISettingResponse(BaseModel):
    id: str
    provider: str
    base_url: Optional[str] = None
    api_key_masked: Optional[str] = None
    model: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AILoadModelsRequest(BaseModel):
    provider: str = Field(default="gemini")
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class AILoadModelsResponse(BaseModel):
    provider: str
    models: List[str] = Field(default_factory=list)


class AITestConnectionRequest(BaseModel):
    provider: str = Field(default="gemini")
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class AITestConnectionResponse(BaseModel):
    success: bool
    provider: str
    base_url: str
    model: str
    latency_ms: int
    reply: Optional[str] = None
    error: Optional[str] = None


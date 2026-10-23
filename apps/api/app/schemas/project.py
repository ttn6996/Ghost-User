"""Project schemas for request validation and serialization."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    base_url: str = Field(..., description="Base target URL for website journeys")
    description: Optional[str] = Field(default=None, max_length=2000, description="Project description")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Base URL must begin with http:// or https://")
        return v


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    base_url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().rstrip("/")
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Base URL must begin with http:// or https://")
        return v


class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

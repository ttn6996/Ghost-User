"""Test Case schemas for request validation and serialization."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from packages.shared.schemas import TestDefinition


class TestCaseBase(BaseModel):
    __test__ = False
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    enabled: bool = True
    definition_json: Dict[str, Any]

    @field_validator("definition_json")
    @classmethod
    def validate_definition(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Validate against strict TestDefinition schema
        try:
            parsed = TestDefinition.model_validate(v)
            return parsed.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid test definition format: {e}")


class TestCaseCreate(TestCaseBase):
    project_id: str


class TestCaseUpdate(BaseModel):
    __test__ = False
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    enabled: Optional[bool] = None
    definition_json: Optional[Dict[str, Any]] = None

    @field_validator("definition_json")
    @classmethod
    def validate_definition(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None:
            try:
                parsed = TestDefinition.model_validate(v)
                return parsed.model_dump()
            except Exception as e:
                raise ValueError(f"Invalid test definition format: {e}")
        return v


class TestCaseValidateRequest(BaseModel):
    __test__ = False
    definition_json: Dict[str, Any]


class TestCaseValidateResponse(BaseModel):
    __test__ = False
    valid: bool
    step_count: int = 0
    errors: list[str] = []


class TestCaseGenerateRequest(BaseModel):
    __test__ = False
    project_id: str
    prompt: str = Field(..., min_length=2, max_length=2000)
    page_path: Optional[str] = Field(default=None, max_length=2048)


class TestCaseGenerateResponse(BaseModel):
    __test__ = False
    suggested_name: str
    suggested_description: str
    steps: list[dict[str, Any]]
    model_used: str
    explanation: str


class TestCaseResponse(TestCaseBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

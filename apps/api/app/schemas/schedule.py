"""Schedule schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict


class ScheduleBase(BaseModel):
    cron_expression: Optional[str] = Field(default=None, max_length=100)
    interval_seconds: Optional[int] = Field(default=None, ge=10, le=86400 * 30)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_schedule_type(self):
        if not self.cron_expression and not self.interval_seconds:
            raise ValueError("Either cron_expression or interval_seconds must be provided")
        return self


class ScheduleCreate(ScheduleBase):
    test_case_id: str


class ScheduleUpdate(BaseModel):
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    id: str
    test_case_id: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

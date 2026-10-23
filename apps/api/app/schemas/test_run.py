"""Test Run schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from packages.shared.constants import RunStatus, StepStatus, TriggerType


class TestStepResultResponse(BaseModel):
    __test__ = False
    id: str
    test_run_id: str
    step_index: int
    action: str
    status: StepStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TestRunCreate(BaseModel):
    __test__ = False
    test_case_id: str
    trigger_type: TriggerType = TriggerType.MANUAL


class TestRunResponse(BaseModel):
    __test__ = False
    id: str
    test_case_id: str
    status: RunStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_summary: Optional[str] = None
    trigger_type: TriggerType
    console_logs_json: Optional[List[Dict[str, Any]]] = None
    page_errors_json: Optional[List[str]] = None
    trace_path: Optional[str] = None
    created_at: datetime
    step_results: List[TestStepResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TestRunListResponse(BaseModel):
    __test__ = False
    items: List[TestRunResponse]
    total: int
    page: int
    page_size: int

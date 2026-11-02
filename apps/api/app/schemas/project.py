"""Project schemas for request validation and serialization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict


import copy
import json
from urllib.parse import urlparse


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    base_url: str = Field(..., description="Base target URL for website journeys")
    description: Optional[str] = Field(default=None, max_length=2000, description="Project description")
    allowed_domains: List[str] = Field(default_factory=list, description="List of authorized hostnames/domains")
    source_code_path: Optional[str] = Field(default=None, max_length=1024, description="Path to source archive or unpacked workspace directory")
    allow_local_loopback: bool = Field(default=False, description="Permit localhost/127.0.0.1 targets in non-production mode")
    execution_mode: str = Field(default="mode_a_manual", description="Execution mode: mode_a_manual or mode_b_auto")
    auth_profile_json: Optional[Any] = Field(default_factory=dict, description="Session injection credentials (cookies, tokens, storage)")
    secrets_json: Optional[Any] = Field(default_factory=dict, description="Key-value dictionary or list of secrets and credentials")
    secrets_masked: bool = Field(default=True, description="Whether to mask secrets in logs, traces, and exports")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Base URL must begin with http:// or https://")
        return v

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, v: List[str]) -> List[str]:
        cleaned = []
        for domain in v:
            d = domain.strip().lower()
            if "://" in d:
                d = urlparse(d).netloc or d
            d = d.split("/")[0].split("?")[0].split("#")[0]
            if d and d not in cleaned:
                cleaned.append(d)
        return cleaned


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    base_url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    allowed_domains: Optional[List[str]] = None
    source_code_path: Optional[str] = None
    allow_local_loopback: Optional[bool] = None
    execution_mode: Optional[str] = None
    auth_profile_json: Optional[Any] = None
    secrets_json: Optional[Any] = None
    secrets_masked: Optional[bool] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().rstrip("/")
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Base URL must begin with http:// or https://")
        return v

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        cleaned = []
        for domain in v:
            d = domain.strip().lower()
            if "://" in d:
                d = urlparse(d).netloc or d
            d = d.split("/")[0].split("?")[0].split("#")[0]
            if d and d not in cleaned:
                cleaned.append(d)
        return cleaned


class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("secrets_json", mode="before")
    @classmethod
    def mask_secrets_in_response(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {k: "***MASKED***" for k in v.keys()}
        elif isinstance(v, list):
            return ["***MASKED***" for _ in v]
        return v or {}

    @field_validator("auth_profile_json", mode="before")
    @classmethod
    def mask_auth_profile_in_response(cls, v: Any) -> Any:
        if not v:
            return {}
        if isinstance(v, str):
            try:
                prof = json.loads(v)
            except Exception:
                return v
        elif isinstance(v, dict):
            prof = copy.deepcopy(v)
        else:
            return v

        if not isinstance(prof, dict):
            return prof

        # 1. Cookies: list or dict
        if "cookies" in prof:
            if isinstance(prof["cookies"], list):
                for cookie in prof["cookies"]:
                    if isinstance(cookie, dict) and "value" in cookie:
                        cookie["value"] = "***MASKED***"
            elif isinstance(prof["cookies"], dict):
                for k in prof["cookies"]:
                    prof["cookies"][k] = "***MASKED***"

        # 2. Headers: dict
        if "headers" in prof and isinstance(prof["headers"], dict):
            for k in prof["headers"]:
                prof["headers"][k] = "***MASKED***"

        # 3. LocalStorage
        if "localStorage" in prof and isinstance(prof["localStorage"], dict):
            for k in prof["localStorage"]:
                prof["localStorage"][k] = "***MASKED***"
        if "local_storage" in prof and isinstance(prof["local_storage"], dict):
            for k in prof["local_storage"]:
                prof["local_storage"][k] = "***MASKED***"

        # 4. Bearer token
        if "bearer_token" in prof and prof["bearer_token"]:
            prof["bearer_token"] = "***MASKED***"

        # 5. Tokens dict
        if "tokens" in prof and isinstance(prof["tokens"], dict):
            for k in prof["tokens"]:
                prof["tokens"][k] = "***MASKED***"

        # 6. Direct root tokens
        for root_key in ("token", "sessionToken", "session_token", "apiKey", "api_key"):
            if root_key in prof and prof[root_key]:
                prof[root_key] = "***MASKED***"

        return prof


class ProjectSourceDirectoryRequest(BaseModel):
    source_directory: str = Field(..., min_length=1, max_length=1024, description="Local path to project source directory")

    @field_validator("source_directory")
    @classmethod
    def validate_source_directory(cls, v: str) -> str:
        v = v.strip()
        if "\x00" in v:
            raise ValueError("Path must not contain null bytes")
        return v


class ProjectSourceUploadResponse(BaseModel):
    project_id: str
    source_code_path: str
    file_name: str
    file_size_bytes: int
    extracted_files_count: int
    message: str


class ProjectSourceInfoResponse(BaseModel):
    project_id: str
    has_source_code: bool
    source_code_path: Optional[str] = None
    files_count: int = 0
    top_level_directories: List[str] = Field(default_factory=list)


class DiscoveryReportResponse(BaseModel):
    id: str
    project_id: str
    status: str
    base_url: str
    pages_count: int
    broken_links_count: int
    forms_count: int
    pages_json: Optional[List[Dict[str, Any]]] = None
    suggested_tests_json: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DiscoverySaveTestRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    steps: List[Dict[str, Any]]


class DevServerStartRequest(BaseModel):
    command: Optional[str] = Field(default=None, max_length=500, description="Custom start command e.g. npm run dev")
    port: Optional[int] = Field(default=None, ge=1024, le=65535, description="Expected server port")
    timeout_seconds: int = Field(default=45, ge=5, le=180)


class AutonomousAuditRequest(BaseModel):
    auto_start_server: bool = Field(default=True, description="Whether to start local dev server if not running")
    max_pages: int = Field(default=15, ge=1, le=30, description="Max pages to crawl and inspect")
    run_form_tests: bool = Field(default=True, description="Whether to generate and execute UI form tests")


class AutonomousAuditResponse(BaseModel):
    project_id: str
    base_url: str
    status: str
    frameworks: List[str] = Field(default_factory=list)
    source_code_path: Optional[str] = None
    dev_server_running: bool = False
    dev_server_url: Optional[str] = None
    static_routes_count: int = 0
    pages_audited_count: int = 0
    broken_links_count: int = 0
    forms_detected_count: int = 0
    console_errors_count: int = 0
    tests_executed_count: int = 0
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    test_runs: List[Dict[str, Any]] = Field(default_factory=list)
    discovery_report_id: Optional[str] = None
    audit_summary: str = ""

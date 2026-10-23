"""Application configuration settings."""

import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Ghost-User"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    DATABASE_URL: str = "sqlite:///./data/ghost_user.db"

    # Storage
    ARTIFACT_STORAGE_DIR: str = "./data/artifacts"

    # Security
    ALLOW_LOCAL_TARGETS: bool = False
    MAX_REDIRECTS: int = 10

    # Worker & Execution (1 active job per worker process for reliable sequential browser execution)
    WORKER_CONCURRENCY: int = 1
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 30000
    ACTION_TIMEOUT_MS: int = 10000
    TRACE_ON_FAILURE: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()

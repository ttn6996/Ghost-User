"""SQLAlchemy database models for Ghost-User."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.session import Base
from packages.shared.constants import RunStatus, StepStatus, TriggerType


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    base_url = Column(String(2048), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    test_cases = relationship("TestCase", back_populates="project", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    definition_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project = relationship("Project", back_populates="test_cases")
    test_runs = relationship("TestRun", back_populates="test_case", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="test_case", cascade="all, delete-orphan")


class TestRun(Base):
    __tablename__ = "test_runs"
    __test__ = False

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_case_id = Column(String(36), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default=RunStatus.QUEUED.value, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_summary = Column(Text, nullable=True)
    trigger_type = Column(String(50), default=TriggerType.MANUAL.value, nullable=False)
    console_logs_json = Column(JSON, nullable=True)
    page_errors_json = Column(JSON, nullable=True)
    trace_path = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    test_case = relationship("TestCase", back_populates="test_runs")
    step_results = relationship(
        "TestStepResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="TestStepResult.step_index",
    )


class TestStepResult(Base):
    __tablename__ = "test_step_results"
    __test__ = False

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_run_id = Column(String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    status = Column(String(50), default=StepStatus.PASSED.value, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String(1024), nullable=True)

    test_run = relationship("TestRun", back_populates="step_results")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_case_id = Column(String(36), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    cron_expression = Column(String(100), nullable=True)
    interval_seconds = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    test_case = relationship("TestCase", back_populates="schedules")

"""Core constants and enum definitions for Ghost-User."""

from enum import Enum


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    API = "api"


class ActionType(str, Enum):
    GOTO = "goto"
    CLICK = "click"
    FILL = "fill"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    WAIT_FOR_VISIBLE = "wait_for_visible"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_TEXT = "assert_text"
    ASSERT_URL = "assert_url"
    SCREENSHOT = "screenshot"

"""Pydantic schemas for test definition validation."""

from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


class BaseAction(BaseModel):
    timeout_ms: Optional[int] = Field(default=10000, ge=500, le=60000)


class GotoAction(BaseAction):
    action: Literal["goto"] = "goto"
    url: str = Field(..., min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_url_syntax(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        # Relative URLs like "/" or "/search" are valid
        # Absolute URLs must start with http:// or https://
        if v.startswith("http://") or v.startswith("https://") or v.startswith("/"):
            return v
        # Relative paths without leading slash are also accepted and will resolve against base_url
        if "://" in v:
            raise ValueError("Only http:// and https:// URL protocols are permitted")
        return "/" + v


class ClickAction(BaseAction):
    action: Literal["click"] = "click"
    selector: str = Field(..., min_length=1, max_length=1000)


class FillAction(BaseAction):
    action: Literal["fill"] = "fill"
    selector: str = Field(..., min_length=1, max_length=1000)
    value: str = Field(default="", max_length=10000)


class SelectOptionAction(BaseAction):
    action: Literal["select_option"] = "select_option"
    selector: str = Field(..., min_length=1, max_length=1000)
    value: str = Field(..., min_length=1, max_length=1000)


class CheckAction(BaseAction):
    action: Literal["check"] = "check"
    selector: str = Field(..., min_length=1, max_length=1000)


class UncheckAction(BaseAction):
    action: Literal["uncheck"] = "uncheck"
    selector: str = Field(..., min_length=1, max_length=1000)


class WaitForVisibleAction(BaseAction):
    action: Literal["wait_for_visible"] = "wait_for_visible"
    selector: str = Field(..., min_length=1, max_length=1000)


class AssertVisibleAction(BaseAction):
    action: Literal["assert_visible"] = "assert_visible"
    selector: str = Field(..., min_length=1, max_length=1000)


class AssertTextAction(BaseAction):
    action: Literal["assert_text"] = "assert_text"
    selector: str = Field(..., min_length=1, max_length=1000)
    expected_text: str = Field(..., min_length=0, max_length=5000)
    exact: bool = False


class AssertUrlAction(BaseAction):
    action: Literal["assert_url"] = "assert_url"
    expected_url: str = Field(..., min_length=1, max_length=2048)


class ScreenshotAction(BaseAction):
    action: Literal["screenshot"] = "screenshot"
    name: Optional[str] = Field(default=None, max_length=100)


TestAction = Annotated[
    Union[
        GotoAction,
        ClickAction,
        FillAction,
        SelectOptionAction,
        CheckAction,
        UncheckAction,
        WaitForVisibleAction,
        AssertVisibleAction,
        AssertTextAction,
        AssertUrlAction,
        ScreenshotAction,
    ],
    Field(discriminator="action"),
]


class TestDefinition(BaseModel):
    __test__ = False
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    steps: list[TestAction] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def validate_steps_not_empty(cls, v: list[TestAction]) -> list[TestAction]:
        if not v:
            raise ValueError("Test definition must contain at least one step")
        return v

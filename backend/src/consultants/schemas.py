"""Validated consultant API contracts."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsultantFields(BaseModel):
    """Fields entered by the operator for a consultant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    post_title: str | None = Field(default=None, max_length=200)

    @field_validator("post_title", mode="before")
    @classmethod
    def blank_optional_text_is_none(cls, value: Any) -> Any:
        """Store an empty post title consistently as null."""

        if isinstance(value, str) and not value.strip():
            return None

        return value


class ConsultantCreate(ConsultantFields):
    """Information accepted when creating a consultant."""


class ConsultantUpdate(ConsultantFields):
    """Complete replacement accepted when editing a consultant."""


class ConsultantRead(ConsultantFields):
    """Consultant information returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )

    id: int

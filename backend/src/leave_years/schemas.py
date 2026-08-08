"""Leave-year API contracts."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class LeaveYearFields(BaseModel):
    """Dates entered when configuring one consultant leave year."""

    start_date: date
    end_date: date
    employment_start: date | None = None
    employment_end: date | None = None

    @model_validator(mode="after")
    def validate_date_order(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("Leave year end date cannot be before its start date")

        for label, value in (
            ("Employment start", self.employment_start),
            ("Employment end", self.employment_end),
        ):
            if value is not None and not self.start_date <= value <= self.end_date:
                raise ValueError(f"{label} must fall inside the leave year")

        if (
            self.employment_start is not None
            and self.employment_end is not None
            and self.employment_end < self.employment_start
        ):
            raise ValueError("Employment end cannot be before employment start")

        return self


class LeaveYearCreate(LeaveYearFields):
    """Information accepted when creating a leave year."""


class LeaveYearUpdate(LeaveYearFields):
    """Complete replacement accepted when editing a leave year."""


class LeaveYearRead(LeaveYearFields):
    """Leave-year information returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    consultant_id: int

"""API contracts for consultant-year carry-forward."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from job_plans.schemas import ExactDecimal


class CarryForwardWrite(BaseModel):
    hours: ExactDecimal = Field(ge=Decimal("0"))


class CarryForwardRead(BaseModel):
    id: int | None
    leave_year_id: int
    hours: ExactDecimal
    created_at: datetime | None

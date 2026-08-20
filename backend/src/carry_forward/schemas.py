"""API contracts for consultant-year carry-forward."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from job_plans.schemas import ExactDecimal


class CarryForwardWrite(BaseModel):
    dcc_hours: ExactDecimal = Field(ge=Decimal("0"))
    spa_hours: ExactDecimal = Field(ge=Decimal("0"))


class CarryForwardRead(BaseModel):
    id: int | None
    leave_year_id: int
    dcc_hours: ExactDecimal
    spa_hours: ExactDecimal
    total_hours: ExactDecimal
    created_at: datetime | None

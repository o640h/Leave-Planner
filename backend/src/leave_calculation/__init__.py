"""Public interface for annual leave calculations."""

from .calculator import (
    calculate_leave_entitlement,
    calculate_partial_year_hours,
    completed_service_years,
    service_anniversary,
)
from .models import (
    LeaveCalculationComponent,
    LeaveCalculationPeriod,
    LeaveCalculationRequest,
    LeaveCalculationResult,
)

__all__ = [
    "LeaveCalculationComponent",
    "LeaveCalculationPeriod",
    "LeaveCalculationRequest",
    "LeaveCalculationResult",
    "calculate_leave_entitlement",
    "calculate_partial_year_hours",
    "completed_service_years",
    "service_anniversary",
]

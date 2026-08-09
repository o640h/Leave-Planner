"""Applied annual-entitlement values used by the leave ledger."""

from dataclasses import dataclass
from enum import StrEnum

from domain import ZERO_HOURS, Hours


class EntitlementMode(StrEnum):
    """How the opening entitlement was chosen by the operator."""

    CALCULATED = "calculated"
    CALCULATED_WITH_OVERRIDE = "calculated_with_override"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class AppliedEntitlement:
    """The final opening hours applied to a consultant's leave ledger."""

    dcc_hours: Hours = ZERO_HOURS
    spa_hours: Hours = ZERO_HOURS
    other_hours: Hours = ZERO_HOURS

    @property
    def total_hours(self) -> Hours:
        return self.dcc_hours + self.spa_hours + self.other_hours

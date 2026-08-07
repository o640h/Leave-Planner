"""Public interface for consultant entitlement policy calculations."""

from domain import ProgrammedActivities

from .hr78_v3 import DEFAULT_ENTITLEMENT_POLICIES, HR78_V3_CONSULTANT_POLICY
from .models import (
    AppointmentEra,
    EntitlementAmount,
    EntitlementComponent,
    EntitlementComponentKind,
    ResolvedEntitlement,
    ServiceTier,
)
from .policy import EntitlementPolicyCatalogue, EntitlementPolicyVersion

__all__ = [
    "DEFAULT_ENTITLEMENT_POLICIES",
    "HR78_V3_CONSULTANT_POLICY",
    "AppointmentEra",
    "EntitlementAmount",
    "EntitlementComponent",
    "EntitlementComponentKind",
    "EntitlementPolicyCatalogue",
    "EntitlementPolicyVersion",
    "ProgrammedActivities",
    "ResolvedEntitlement",
    "ServiceTier",
]

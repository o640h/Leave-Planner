"""Value objects used by consultant entitlement policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from domain import ZERO_HOURS, Hours, ProgrammedActivities, RuleId


class EntitlementComponentKind(StrEnum):
    """Categories used to explain an annual entitlement."""

    CORE = "core"
    STATUTORY = "statutory"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class EntitlementComponent:
    """One whole-time entitlement component defined by policy."""

    rule_id: RuleId
    label: str
    kind: EntitlementComponentKind
    full_time_hours: Hours

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("Entitlement component label cannot be empty")
        if self.full_time_hours.value < 0:
            raise ValueError("Entitlement component hours cannot be negative")


@dataclass(frozen=True, slots=True)
class ServiceTier:
    """An entitlement tier reached after completed service in grade."""

    rule_id: RuleId
    minimum_completed_years: int
    components: tuple[EntitlementComponent, ...]

    def __post_init__(self) -> None:
        if self.minimum_completed_years < 0:
            raise ValueError("Minimum completed years cannot be negative")
        if not self.components:
            raise ValueError("A service tier must contain at least one entitlement component")


@dataclass(frozen=True, slots=True)
class AppointmentEra:
    """Service tiers applying to a range of consultant appointment dates."""

    rule_id: RuleId
    label: str
    appointment_from: date | None
    appointment_to: date | None
    service_tiers: tuple[ServiceTier, ...]

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("Appointment era label cannot be empty")
        if (
            self.appointment_from is not None
            and self.appointment_to is not None
            and self.appointment_to < self.appointment_from
        ):
            raise ValueError("Appointment era end date cannot be before its start date")
        if not self.service_tiers:
            raise ValueError("An appointment era must contain at least one service tier")

        thresholds = tuple(tier.minimum_completed_years for tier in self.service_tiers)
        if thresholds[0] != 0:
            raise ValueError("The first service tier must begin at zero years")
        if thresholds != tuple(sorted(set(thresholds))):
            raise ValueError("Service tiers must have unique ascending thresholds")

    def includes(self, appointment_date: date) -> bool:
        """Return whether an appointment date belongs to this era."""

        starts_in_time = self.appointment_from is None or appointment_date >= self.appointment_from
        ends_in_time = self.appointment_to is None or appointment_date <= self.appointment_to
        return starts_in_time and ends_in_time

    def tier_for(self, completed_service_years: int) -> ServiceTier:
        """Select the highest service tier already reached."""

        if completed_service_years < 0:
            raise ValueError("Completed service years cannot be negative")

        eligible_tiers = tuple(
            tier
            for tier in self.service_tiers
            if tier.minimum_completed_years <= completed_service_years
        )
        return eligible_tiers[-1]

    @property
    def service_milestones(self) -> tuple[int, ...]:
        """Return service thresholds after the initial zero-year tier."""

        return tuple(
            tier.minimum_completed_years
            for tier in self.service_tiers
            if tier.minimum_completed_years > 0
        )


@dataclass(frozen=True, slots=True)
class EntitlementAmount:
    """A policy component after PA capping and proration."""

    component: EntitlementComponent
    adjusted_hours: Hours


@dataclass(frozen=True, slots=True)
class ResolvedEntitlement:
    """The annual entitlement rate selected for one point in time."""

    policy_version: str
    appointment_era: AppointmentEra
    service_tier: ServiceTier
    contracted_pas: ProgrammedActivities
    capped_pas: ProgrammedActivities
    proration_factor: Decimal
    components: tuple[EntitlementAmount, ...]

    @property
    def full_time_hours(self) -> Hours:
        """Return entitlement before PA-based proration."""

        total = ZERO_HOURS
        for amount in self.components:
            total += amount.component.full_time_hours
        return total

    @property
    def annual_hours(self) -> Hours:
        """Return entitlement after PA-based proration."""

        total = ZERO_HOURS
        for amount in self.components:
            total += amount.adjusted_hours
        return total


def periods_overlap(
    first_from: date | None,
    first_to: date | None,
    second_from: date | None,
    second_to: date | None,
) -> bool:
    """Return whether two inclusive, potentially open date ranges overlap."""

    first_start = first_from or date.min
    first_end = first_to or date.max
    second_start = second_from or date.min
    second_end = second_to or date.max
    return first_start <= second_end and second_start <= first_end

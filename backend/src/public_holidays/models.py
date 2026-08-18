"""Public-holiday calendar and calculation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from domain import ZERO_HOURS, DateRange, Hours, ProgrammedActivities, RuleId
from job_plans import JobPlanHistory


class HolidayCalendarSource(StrEnum):
    """Where the base public-holiday calendar came from."""

    STATIC_SNAPSHOT = "static_snapshot"
    GOV_UK_SYNC = "gov_uk_sync"


class HolidayCorrectionAction(StrEnum):
    """Supported manual changes to a base calendar."""

    ADD_OR_REPLACE = "add_or_replace"
    REMOVE = "remove"


class HolidayTreatmentBasis(StrEnum):
    """How a consultant's public holiday should be treated."""

    STANDARD = "standard"
    QUALIFYING_ON_CALL = "qualifying_on_call"


@dataclass(frozen=True, slots=True)
class PublicHoliday:
    """One officially designated public holiday."""

    holiday_date: date
    name: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Public-holiday name cannot be empty")


@dataclass(frozen=True, slots=True)
class PublicHolidayCorrection:
    """One explicit Trust-specific calendar correction."""

    holiday_date: date
    action: HolidayCorrectionAction
    reason: str
    replacement_name: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("Correction reason cannot be empty")

        if self.action is HolidayCorrectionAction.ADD_OR_REPLACE:
            if not self.replacement_name or not self.replacement_name.strip():
                raise ValueError("An add-or-replace correction requires a name")
        elif self.replacement_name is not None:
            raise ValueError("A remove correction cannot have a replacement name")


@dataclass(frozen=True, slots=True)
class PublicHolidayCalendar:
    """A dated England and Wales calendar plus manual corrections."""

    source: HolidayCalendarSource
    source_date: date
    holidays: tuple[PublicHoliday, ...]
    corrections: tuple[PublicHolidayCorrection, ...] = ()

    def __post_init__(self) -> None:
        holiday_dates = tuple(holiday.holiday_date for holiday in self.holidays)
        if holiday_dates != tuple(sorted(holiday_dates)):
            raise ValueError("Calendar holidays must be in chronological order")

        if len(holiday_dates) != len(set(holiday_dates)):
            raise ValueError("Calendar cannot contain duplicate holiday dates")

        correction_dates = tuple(correction.holiday_date for correction in self.corrections)
        if len(correction_dates) != len(set(correction_dates)):
            raise ValueError("Calendar cannot contain multiple corrections for the same date")


@dataclass(frozen=True, slots=True)
class PublicHolidayTreatment:
    """Operator-selected treatment of one consultant's holiday."""

    holiday_date: date
    basis: HolidayTreatmentBasis
    note: str | None = None

    def __post_init__(self) -> None:
        if self.note is not None and not self.note.strip():
            raise ValueError("Treatment note cannot be blank")

    @property
    def retains_leave(self) -> bool:
        """Return whether the normal holiday deduction is retained."""

        return self.basis is HolidayTreatmentBasis.QUALIFYING_ON_CALL


@dataclass(frozen=True, slots=True)
class PublicHolidayRequest:
    """Inputs for one consultant's public-holiday calculation."""

    leave_year: DateRange
    employment_start: date
    employment_end: date | None
    calendar: PublicHolidayCalendar
    job_plans: JobPlanHistory
    treatments: tuple[PublicHolidayTreatment, ...] = ()

    def __post_init__(self) -> None:
        if self.employment_end is not None and self.employment_end < self.employment_start:
            raise ValueError("employment_end cannot be before employment_start")

        treatment_dates = tuple(treatment.holiday_date for treatment in self.treatments)
        if len(treatment_dates) != len(set(treatment_dates)):
            raise ValueError("A holiday cannot have more than one treatment")

    @property
    def active_period(self) -> DateRange | None:
        """Return employment clipped to the leave year."""

        start = max(
            self.leave_year.start,
            self.employment_start,
        )
        end = min(
            self.leave_year.end,
            self.employment_end or self.leave_year.end,
        )

        if end < start:
            return None

        return DateRange(start, end)


@dataclass(frozen=True, slots=True)
class PublicHolidayOccurrence:
    """Calculated entitlement and deduction for one holiday."""

    holiday: PublicHoliday
    job_plan_version: RuleId
    contracted_pas: ProgrammedActivities
    capped_pas: ProgrammedActivities
    pa_factor: Decimal
    deduction_factor: Decimal
    entitlement_hours: Hours
    dcc_entitlement_hours: Hours
    spa_entitlement_hours: Hours
    other_entitlement_hours: Hours
    treatment: PublicHolidayTreatment
    dcc_deduction_hours: Hours
    spa_deduction_hours: Hours
    other_deduction_hours: Hours

    @property
    def deduction_hours(self) -> Hours:
        return self.dcc_deduction_hours + self.spa_deduction_hours + self.other_deduction_hours


@dataclass(frozen=True, slots=True)
class PublicHolidayResult:
    """All applicable holidays and their totals."""

    occurrences: tuple[PublicHolidayOccurrence, ...]

    @property
    def entitlement_hours(self) -> Hours:
        return self._sum("entitlement_hours")

    @property
    def dcc_entitlement_hours(self) -> Hours:
        return self._sum("dcc_entitlement_hours")

    @property
    def spa_entitlement_hours(self) -> Hours:
        return self._sum("spa_entitlement_hours")

    @property
    def other_entitlement_hours(self) -> Hours:
        return self._sum("other_entitlement_hours")

    @property
    def deduction_hours(self) -> Hours:
        total = ZERO_HOURS

        for occurrence in self.occurrences:
            total += occurrence.deduction_hours

        return total

    def _sum(self, field_name: str) -> Hours:
        total = ZERO_HOURS

        for occurrence in self.occurrences:
            total += getattr(occurrence, field_name)

        return total

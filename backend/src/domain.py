"""Core value objects used by leave calculations."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from types import MappingProxyType
from typing import Generic, TypeAlias, TypeVar

DecimalInput: TypeAlias = Decimal | int | str
ResultValue = TypeVar("ResultValue")

def _to_decimal(value: DecimalInput, *, field_name: str) -> Decimal:
    """Convert an exact input into a finite Decimal."""

    if isinstance(value, (bool, float)):
        raise TypeError(f"{field_name} cannot be created from bool or float")

    try:
        if isinstance(value, Decimal):
            result = value
        elif isinstance(value, int):
            result = Decimal(value)
        else:
            result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field_name} is not a valid decimal value") from error

    if not result.is_finite():
        raise ValueError(f"{field_name} must be a finite decimal value")

    return result


@dataclass(frozen=True, order=True, slots=True)
class Hours:
    """An exact, potentially signed quantity of hours."""

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError(
                "Hours must be constructed with Decimal: "
                "use Hours.from_value for strings or integers"
            )

        if not self.value.is_finite():
            raise ValueError("Hours must be a finite decimal value")

    @classmethod
    def from_value(cls, value: DecimalInput) -> Hours:
        """Construct hours from a string, integer, or Decimal."""
        return cls(_to_decimal(value, field_name="Hours"))

    def __add__(self, other: Hours) -> Hours:
        return Hours(self.value + other.value)

    def __sub__(self, other: Hours) -> Hours:
        return Hours(self.value - other.value)

    def __neg__(self) -> Hours:
        return Hours(-self.value)

    def scale(self, factor: DecimalInput) -> Hours:
        """Scale the hours by a given factor."""
        decimal_factor = _to_decimal(factor, field_name="Scale factor")
        return Hours(self.value * decimal_factor)

    def ratio_of(self, total: Hours) -> Decimal:
        if total.value == 0:
            raise ZeroDivisionError("Cannot calculate a ratio against zero hours")

        return self.value / total.value

    def __str__(self) -> str:
        return format(self.value, "f")


@dataclass(frozen=True, order=True, slots=True)
class ProgrammedActivities:
    """An exact number of contracted programmed activities."""

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError(
                "ProgrammedActivities must be constructed with Decimal: "
                "use ProgrammedActivities.from_value for strings or integers"
            )

        if not self.value.is_finite():
            raise ValueError("Programmed activities must be finite")

        if self.value < 0:
            raise ValueError("Programmed activities cannot be negative")

    @classmethod
    def from_value(cls, value: DecimalInput) -> ProgrammedActivities:
        """Construct programmed activities from an exact input."""

        return cls(
            _to_decimal(
                value,
                field_name="Programmed activities",
            )
        )

    def __str__(self) -> str:
        return format(self.value, "f")


ZERO_HOURS = Hours(Decimal("0"))


@dataclass(frozen=True, slots=True)
class DateRange:
    """An inclusive range of calendar dates."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if type(self.start) is not date or type(self.end) is not date:
            raise TypeError("DateRange boundaries must be dates, not datetimes")

        if self.end < self.start:
            raise ValueError("DateRange end date must not be before start date")

    @property
    def calendar_days(self) -> int:
        """Return the number of calendar days in the range."""
        return (self.end - self.start).days + 1

    def dates(self) -> Iterator[date]:
        """Yield each date in the range, inclusive."""
        for offset in range(self.calendar_days):
            yield self.start + timedelta(days=offset)

    def __contains__(self, value: object) -> bool:
        return (
            type(value) is date
            and self.start <= value
            and value <= self.end
        )


class ActivityType(StrEnum):
    """Activity categories recorded in consultant job plans."""

    DCC = "dcc"
    SPA = "spa"
    OTHER = "other"


class LeaveState(StrEnum):
    """Lifecycle states for a leave booking."""

    PLANNED = "planned"
    APPROVED = "approved"
    TAKEN = "taken"
    CANCELLED = "cancelled"


class WarningSeverity(StrEnum):
    """Severity levels for non-blocking calculation warnings."""

    INFO = "info"
    WARNING = "warning"


_RULE_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)


@dataclass(frozen=True, order=True, slots=True)
class RuleId:
    """A stable, machine-readable calculation or quality-rule identifier."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("RuleId must be constructed with a string")

        if not _RULE_ID_PATTERN.fullmatch(self.value):
            raise ValueError(
                "RuleId must be lowercase and contain only alphanumeric "
                "sections separated by '.', '_' or '-'"
            )

    def __str__(self) -> str:
        return self.value


def _immutable_context(context: Mapping[str, str]) -> Mapping[str, str]:
    """Copy calculation metadata into an immutable mapping."""

    copied_context = dict(context)

    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in copied_context.items()
    ):
        raise TypeError("Context keys and values must be strings")

    return MappingProxyType(copied_context)


@dataclass(frozen=True, slots=True)
class CalculationWarning:
    """A non-blocking, traceable issue produced by a calculation."""

    rule_id: RuleId
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING
    affected_period: DateRange | None = None
    context: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, RuleId):
            raise TypeError("CalculationWarning rule_id must be a RuleId")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("CalculationWarning message must be a non-empty string")

        if not isinstance(self.severity, WarningSeverity):
            raise TypeError("CalculationWarning severity must be a WarningSeverity")

        if (
            self.affected_period is not None
            and not isinstance(self.affected_period, DateRange)
        ):
            raise TypeError("CalculationWarning affected_period must be a DateRange")

        object.__setattr__(self, "context", _immutable_context(self.context))


@dataclass(frozen=True, slots=True)
class CalculationStep:
    """One auditable step in a calculation trace."""

    rule_id: RuleId
    description: str
    amount: Hours | None = None
    effective_date: date | None = None
    context: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, RuleId):
            raise TypeError("CalculationStep rule_id must be a RuleId")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("CalculationStep description must be a non-empty string")

        if self.amount is not None and not isinstance(self.amount, Hours):
            raise TypeError("CalculationStep amount must be an Hours instance")

        if self.effective_date is not None and type(self.effective_date) is not date:
            raise TypeError("CalculationStep effective_date must be a date")

        object.__setattr__(self, "context", _immutable_context(self.context))


@dataclass(frozen=True, slots=True)
class CalculationResult(Generic[ResultValue]):
    """A value together with its warnings and calculation trace."""

    value: ResultValue
    warnings: tuple[CalculationWarning, ...] = ()
    trace: tuple[CalculationStep, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.warnings, tuple):
            raise TypeError("CalculationResult warnings must be a tuple")

        if any(
            not isinstance(warning, CalculationWarning)
            for warning in self.warnings
        ):
            raise TypeError(
                "CalculationResult warnings must contain "
                "CalculationWarning instances"
            )

        if not isinstance(self.trace, tuple):
            raise TypeError("CalculationResult trace must be a tuple")

        if any(
            not isinstance(step, CalculationStep)
            for step in self.trace
        ):
            raise TypeError(
                "CalculationResult trace must contain "
                "CalculationStep instances"
            )

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)
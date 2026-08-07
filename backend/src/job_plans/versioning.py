"""Effective-dated job-plan versions and history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain import RuleId

from .models import JobPlanCycle, JobPlanDay, Weekday


def _periods_overlap(
    first_from: date,
    first_to: date | None,
    second_from: date,
    second_to: date | None,
) -> bool:
    """Return whether two inclusive effective periods overlap."""

    first_end = first_to or date.max
    second_end = second_to or date.max

    return first_from <= second_end and second_from <= first_end


@dataclass(frozen=True, slots=True)
class JobPlanVersion:
    """One effective-dated repeating job plan."""

    version_id: RuleId
    effective_from: date
    effective_to: date | None
    cycle_anchor_date: date
    cycle: JobPlanCycle

    def __post_init__(self) -> None:
        if not isinstance(self.version_id, RuleId):
            raise TypeError("Job-plan version_id must be a RuleId")

        if type(self.effective_from) is not date:
            raise TypeError("effective_from must be a date")

        if self.effective_to is not None and type(self.effective_to) is not date:
            raise TypeError("effective_to must be a date")

        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")

        if type(self.cycle_anchor_date) is not date:
            raise TypeError("cycle_anchor_date must be a date")

        if self.cycle_anchor_date.weekday() != Weekday.MONDAY:
            raise ValueError("Cycle anchor date must be a Monday")

        if self.cycle_anchor_date > self.effective_from:
            raise ValueError("Cycle anchor date cannot be after effective_from")

        if not isinstance(self.cycle, JobPlanCycle):
            raise TypeError("cycle must be a JobPlanCycle")

    def includes(self, target_date: date) -> bool:
        """Return whether this version applies on a date."""

        if type(target_date) is not date:
            raise TypeError("Target date must be a date")

        return target_date >= self.effective_from and (
            self.effective_to is None or target_date <= self.effective_to
        )

    def day_on(self, target_date: date) -> JobPlanDay:
        """Return the planned day for an effective calendar date."""

        if not self.includes(target_date):
            raise ValueError("Job-plan version does not apply on target date")

        return self.cycle.day_on(
            target_date,
            cycle_anchor_date=self.cycle_anchor_date,
        )


@dataclass(frozen=True, slots=True)
class JobPlanHistory:
    """A consultant's chronological job-plan versions."""

    versions: tuple[JobPlanVersion, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.versions, tuple):
            raise TypeError("Job-plan history versions must be a tuple")

        if not self.versions:
            raise ValueError("Job-plan history must contain at least one version")

        if any(not isinstance(version, JobPlanVersion) for version in self.versions):
            raise TypeError("Job-plan history must contain JobPlanVersion instances")

        ordered_versions = tuple(
            sorted(
                self.versions,
                key=lambda version: version.effective_from,
            )
        )

        if self.versions != ordered_versions:
            raise ValueError("Job-plan versions must be in chronological order")

        for index, first_version in enumerate(self.versions):
            for second_version in self.versions[index + 1 :]:
                if _periods_overlap(
                    first_version.effective_from,
                    first_version.effective_to,
                    second_version.effective_from,
                    second_version.effective_to,
                ):
                    raise ValueError("Job-plan versions cannot overlap")

    def version_on(self, target_date: date) -> JobPlanVersion:
        """Return the single job-plan version applying on a date."""

        matching_versions = tuple(
            version for version in self.versions if version.includes(target_date)
        )

        if len(matching_versions) != 1:
            raise LookupError("Target date must match exactly one job-plan version")

        return matching_versions[0]

    def day_on(self, target_date: date) -> JobPlanDay:
        """Resolve both the effective version and cycle day."""

        return self.version_on(target_date).day_on(target_date)

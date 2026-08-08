"""Version selection and entitlement resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain import CalculationResult, CalculationStep, Hours, ProgrammedActivities, RuleId

from .models import (
    AppointmentEra,
    EntitlementAmount,
    EntitlementComponent,
    ResolvedEntitlement,
    periods_overlap,
)


@dataclass(frozen=True, slots=True)
class EntitlementPolicyVersion:
    """One immutable, effective-dated entitlement policy snapshot."""

    version: str
    source_document: str
    source_section: str
    effective_from: date
    effective_to: date | None
    hours_per_pa: Hours
    pa_cap: ProgrammedActivities
    common_components: tuple[EntitlementComponent, ...]
    appointment_eras: tuple[AppointmentEra, ...]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("Policy version cannot be empty")
        if not self.source_document.strip():
            raise ValueError("Policy source document cannot be empty")
        if not self.source_section.strip():
            raise ValueError("Policy source section cannot be empty")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Policy effective_to cannot be before effective_from")
        if self.hours_per_pa.value <= 0:
            raise ValueError("hours_per_pa must be greater than zero")
        if self.pa_cap.value <= 0:
            raise ValueError("pa_cap must be greater than zero")
        if not self.appointment_eras:
            raise ValueError("A policy version must contain at least one appointment era")

        self._validate_appointment_eras()
        self._validate_component_ids()

    def _validate_appointment_eras(self) -> None:
        for index, first_era in enumerate(self.appointment_eras):
            for second_era in self.appointment_eras[index + 1 :]:
                if periods_overlap(
                    first_era.appointment_from,
                    first_era.appointment_to,
                    second_era.appointment_from,
                    second_era.appointment_to,
                ):
                    raise ValueError("Appointment eras must not have overlapping dates")

    def _validate_component_ids(self) -> None:
        for era in self.appointment_eras:
            for tier in era.service_tiers:
                component_ids = tuple(
                    component.rule_id for component in self.common_components + tier.components
                )
                if len(component_ids) != len(set(component_ids)):
                    raise ValueError("Resolved entitlement component IDs must be unique")

    def applies_on(self, calculation_date: date) -> bool:
        """Return whether this policy version applies on a date."""

        return calculation_date >= self.effective_from and (
            self.effective_to is None or calculation_date <= self.effective_to
        )

    def resolve(
        self,
        *,
        calculation_date: date,
        consultant_appointment_date: date,
        completed_service_years: int,
        contracted_pas: ProgrammedActivities,
    ) -> CalculationResult[ResolvedEntitlement]:
        """Resolve the annual entitlement rate for one effective date."""

        if not self.applies_on(calculation_date):
            raise ValueError(
                f"Policy version {self.version!r} does not apply on {calculation_date.isoformat()}"
            )
        matching_eras = tuple(
            era for era in self.appointment_eras if era.includes(consultant_appointment_date)
        )
        if len(matching_eras) != 1:
            raise ValueError("Consultant appointment date must match exactly one appointment era")

        appointment_era = matching_eras[0]
        service_tier = appointment_era.tier_for(completed_service_years)
        capped_pas = ProgrammedActivities(min(contracted_pas.value, self.pa_cap.value))
        proration_factor = capped_pas.value / self.pa_cap.value
        policy_components = self.common_components + service_tier.components
        amounts = tuple(
            EntitlementAmount(
                component=component,
                adjusted_hours=component.full_time_hours.scale(proration_factor),
            )
            for component in policy_components
        )

        resolved = ResolvedEntitlement(
            policy_version=self.version,
            appointment_era=appointment_era,
            service_tier=service_tier,
            contracted_pas=contracted_pas,
            capped_pas=capped_pas,
            proration_factor=proration_factor,
            components=amounts,
        )
        return CalculationResult(value=resolved, trace=self._trace(resolved, calculation_date))

    def _trace(
        self,
        resolved: ResolvedEntitlement,
        calculation_date: date,
    ) -> tuple[CalculationStep, ...]:
        return (
            CalculationStep(
                rule_id=resolved.appointment_era.rule_id,
                description="Selected consultant appointment-era rules",
                effective_date=calculation_date,
                context={"appointment_era": resolved.appointment_era.label},
            ),
            CalculationStep(
                rule_id=resolved.service_tier.rule_id,
                description="Selected completed-service entitlement tier",
                amount=resolved.full_time_hours,
                effective_date=calculation_date,
                context={
                    "minimum_completed_years": str(resolved.service_tier.minimum_completed_years)
                },
            ),
            CalculationStep(
                rule_id=RuleId("entitlement.pa-proration"),
                description="Applied the contracted PA cap and proration",
                amount=resolved.annual_hours,
                effective_date=calculation_date,
                context={
                    "contracted_pas": str(resolved.contracted_pas),
                    "capped_pas": str(resolved.capped_pas),
                    "pa_cap": str(self.pa_cap),
                    "proration_factor": format(resolved.proration_factor, "f"),
                },
            ),
        )


@dataclass(frozen=True, slots=True)
class EntitlementPolicyCatalogue:
    """An ordered collection of non-overlapping policy versions."""

    versions: tuple[EntitlementPolicyVersion, ...]

    def __post_init__(self) -> None:
        if not self.versions:
            raise ValueError("The entitlement policy catalogue cannot be empty")

        ordered_versions = tuple(sorted(self.versions, key=lambda version: version.effective_from))
        if self.versions != ordered_versions:
            raise ValueError("Policy versions must be ordered by effective_from")

        for index, first_version in enumerate(self.versions):
            for second_version in self.versions[index + 1 :]:
                if periods_overlap(
                    first_version.effective_from,
                    first_version.effective_to,
                    second_version.effective_from,
                    second_version.effective_to,
                ):
                    raise ValueError("Policy versions must not have overlapping dates")

    def version_on(self, calculation_date: date) -> EntitlementPolicyVersion:
        """Return the single policy version applying on a date."""

        matching_versions = tuple(
            version for version in self.versions if version.applies_on(calculation_date)
        )
        if len(matching_versions) != 1:
            raise LookupError("Calculation date must match exactly one policy version")
        return matching_versions[0]

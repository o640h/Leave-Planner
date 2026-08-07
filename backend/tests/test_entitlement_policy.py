"""Tests for versioned consultant entitlement policy rules.

The first group reads like policy examples and checks the HR78 table directly.
The remaining tests protect the validation rules used when future policy
versions are created or loaded from storage.
"""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from domain import Hours, RuleId
from entitlement_policy import (
    DEFAULT_ENTITLEMENT_POLICIES,
    HR78_V3_CONSULTANT_POLICY,
    AppointmentEra,
    EntitlementComponent,
    EntitlementComponentKind,
    EntitlementPolicyCatalogue,
    EntitlementPolicyVersion,
    ProgrammedActivities,
    ResolvedEntitlement,
    ServiceTier,
)
from entitlement_policy.models import periods_overlap

POLICY_DATE = date(2025, 7, 1)
TEST_COMPONENT_ID = RuleId("test.component")
TEST_COMPONENT_HOURS = Hours.from_value("8")
TEST_TIER_ID = RuleId("test.tier")
TEST_ERA_ID = RuleId("test.era")


def _resolve(
    appointment_date: date,
    completed_years: int,
    contracted_pas: str = "10",
) -> ResolvedEntitlement:
    """Resolve HR78 using exact string input for the contracted PAs."""

    result = HR78_V3_CONSULTANT_POLICY.resolve(
        calculation_date=POLICY_DATE,
        consultant_appointment_date=appointment_date,
        completed_service_years=completed_years,
        contracted_pas=ProgrammedActivities.from_value(contracted_pas),
    )
    return result.value


@pytest.mark.parametrize(
    ("appointment_date", "completed_years", "expected_hours"),
    [
        # The exact dates around each boundary prevent a one-day policy gap.
        (date(2004, 3, 31), 20, "272"),
        (date(2004, 4, 1), 6, "272"),
        (date(2004, 4, 1), 7, "280"),
        (date(2005, 3, 31), 7, "280"),
        (date(2005, 4, 1), 6, "272"),
        (date(2005, 4, 1), 7, "288"),
    ],
)
def test_hr78_appointment_eras_and_service_tiers(
    appointment_date: date,
    completed_years: int,
    expected_hours: str,
) -> None:
    """HR78 section 7.4 must resolve to its published hour totals."""

    assert _resolve(appointment_date, completed_years).annual_hours == Hours.from_value(
        expected_hours
    )


@pytest.mark.parametrize(
    ("contracted_pas", "expected_factor", "expected_hours"),
    [
        ("0", "0", "0"),
        ("6", "0.6", "172.8"),
        ("8.47", "0.847", "243.936"),
        ("10", "1", "288"),
        # A 12-PA job plan receives no more entitlement than a 10-PA plan.
        ("12", "1", "288"),
    ],
)
def test_pa_proration_is_exact_and_capped_at_ten(
    contracted_pas: str,
    expected_factor: str,
    expected_hours: str,
) -> None:
    resolved = _resolve(date(2010, 1, 1), 7, contracted_pas)

    assert resolved.proration_factor == Decimal(expected_factor)
    assert resolved.annual_hours == Hours.from_value(expected_hours)
    assert resolved.capped_pas.value <= Decimal("10")


def test_resolved_entitlement_retains_explainable_components_and_trace() -> None:
    """A displayed total must remain traceable to policy and PA decisions."""

    result = HR78_V3_CONSULTANT_POLICY.resolve(
        calculation_date=POLICY_DATE,
        consultant_appointment_date=date(2010, 1, 1),
        completed_service_years=7,
        contracted_pas=ProgrammedActivities.from_value("8.47"),
    )
    component_hours = {
        amount.component.kind: amount.adjusted_hours for amount in result.value.components
    }

    assert result.value.full_time_hours == Hours.from_value("288")
    assert component_hours == {
        EntitlementComponentKind.STATUTORY: Hours.from_value("13.552"),
        EntitlementComponentKind.LOCAL: Hours.from_value("13.552"),
        EntitlementComponentKind.CORE: Hours.from_value("216.832"),
    }
    assert len(result.trace) == 3
    assert result.trace[-1].context["proration_factor"] == "0.847"
    assert result.trace[-1].amount == Hours.from_value("243.936")


def test_default_catalogue_selects_the_effective_policy() -> None:
    selected = DEFAULT_ENTITLEMENT_POLICIES.version_on(POLICY_DATE)

    assert selected is HR78_V3_CONSULTANT_POLICY
    assert selected.hours_per_pa == Hours.from_value("4")
    assert selected.pa_cap == ProgrammedActivities.from_value("10")


def test_service_milestones_exclude_the_initial_tier() -> None:
    modern_era = HR78_V3_CONSULTANT_POLICY.appointment_eras[-1]

    assert modern_era.service_milestones == (7,)
    assert modern_era.tier_for(6).minimum_completed_years == 0
    assert modern_era.tier_for(7).minimum_completed_years == 7


def test_programmed_activities_preserve_exact_decimal_input() -> None:
    pas = ProgrammedActivities.from_value("8.470")

    assert pas.value == Decimal("8.470")
    assert str(pas) == "8.470"


@pytest.mark.parametrize("unsafe_value", [8.47, True, False])
def test_programmed_activities_reject_floats_and_booleans(unsafe_value: Any) -> None:
    with pytest.raises(TypeError, match="bool or float"):
        ProgrammedActivities.from_value(unsafe_value)


@pytest.mark.parametrize("invalid_value", ["not-a-number", Decimal("NaN")])
def test_programmed_activities_reject_invalid_or_non_finite_values(
    invalid_value: Any,
) -> None:
    with pytest.raises(ValueError):
        ProgrammedActivities.from_value(invalid_value)


def test_programmed_activities_reject_negative_and_unwrapped_values() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        ProgrammedActivities.from_value("-0.1")
    with pytest.raises(TypeError, match="constructed with Decimal"):
        ProgrammedActivities(cast(Any, "10"))


def test_appointment_era_includes_only_its_inclusive_date_range() -> None:
    transition_era = HR78_V3_CONSULTANT_POLICY.appointment_eras[1]

    assert transition_era.includes(date(2004, 4, 1))
    assert transition_era.includes(date(2005, 3, 31))
    assert not transition_era.includes(date(2004, 3, 31))
    assert not transition_era.includes(date(2005, 4, 1))


def test_open_and_closed_period_overlap_detection() -> None:
    """Version and appointment boundaries are inclusive at both ends."""

    assert periods_overlap(None, date(2025, 1, 1), date(2025, 1, 1), None)
    assert not periods_overlap(
        None,
        date(2024, 12, 31),
        date(2025, 1, 1),
        None,
    )


def _component(
    *,
    rule_id: RuleId = TEST_COMPONENT_ID,
    label: str = "Test component",
    kind: EntitlementComponentKind = EntitlementComponentKind.CORE,
    hours: Hours = TEST_COMPONENT_HOURS,
) -> EntitlementComponent:
    return EntitlementComponent(
        rule_id=rule_id,
        label=label,
        kind=kind,
        full_time_hours=hours,
    )


def _tier(
    *,
    rule_id: RuleId = TEST_TIER_ID,
    years: int = 0,
    components: tuple[EntitlementComponent, ...] | None = None,
) -> ServiceTier:
    return ServiceTier(
        rule_id=rule_id,
        minimum_completed_years=years,
        components=components or (_component(),),
    )


def _era(
    *,
    rule_id: RuleId = TEST_ERA_ID,
    appointment_from: date | None = None,
    appointment_to: date | None = None,
    tiers: tuple[ServiceTier, ...] | None = None,
) -> AppointmentEra:
    return AppointmentEra(
        rule_id=rule_id,
        label="Test era",
        appointment_from=appointment_from,
        appointment_to=appointment_to,
        service_tiers=tiers or (_tier(),),
    )


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"rule_id": cast(Any, "bad")}, TypeError, "rule_id"),
        ({"label": " "}, ValueError, "label"),
        ({"kind": cast(Any, "core")}, TypeError, "kind"),
        ({"full_time_hours": cast(Any, 8)}, TypeError, "full_time_hours"),
        ({"full_time_hours": Hours.from_value("-1")}, ValueError, "cannot be negative"),
    ],
)
def test_entitlement_component_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_component(), **changes)


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"rule_id": cast(Any, "bad")}, TypeError, "rule_id"),
        ({"minimum_completed_years": cast(Any, True)}, TypeError, "integer"),
        ({"minimum_completed_years": -1}, ValueError, "cannot be negative"),
        ({"components": ()}, ValueError, "at least one"),
        ({"components": cast(Any, ("bad",))}, TypeError, "components"),
    ],
)
def test_service_tier_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_tier(), **changes)


def test_service_tier_rejects_invalid_completed_years() -> None:
    tiered_era = _era(tiers=(_tier(), _tier(rule_id=RuleId("test.tier.7"), years=7)))

    with pytest.raises(TypeError, match="integer"):
        tiered_era.tier_for(cast(Any, True))
    with pytest.raises(ValueError, match="cannot be negative"):
        tiered_era.tier_for(-1)


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"rule_id": cast(Any, "bad")}, TypeError, "rule_id"),
        ({"label": ""}, ValueError, "label"),
        ({"appointment_from": cast(Any, datetime(2025, 1, 1))}, TypeError, "appointment_from"),
        ({"appointment_to": cast(Any, datetime(2025, 1, 1))}, TypeError, "appointment_to"),
        (
            {"appointment_from": date(2025, 2, 1), "appointment_to": date(2025, 1, 1)},
            ValueError,
            "before",
        ),
        ({"service_tiers": ()}, ValueError, "at least one"),
        ({"service_tiers": cast(Any, ("bad",))}, TypeError, "tiers"),
        ({"service_tiers": (_tier(years=1),)}, ValueError, "zero years"),
        (
            {
                "service_tiers": (
                    _tier(),
                    _tier(rule_id=RuleId("test.tier.duplicate")),
                )
            },
            ValueError,
            "unique ascending",
        ),
    ],
)
def test_appointment_era_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(_era(), **changes)


def test_appointment_era_rejects_datetime_lookup() -> None:
    with pytest.raises(TypeError, match="must be a date"):
        _era().includes(cast(Any, datetime(2025, 1, 1)))


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"version": ""}, ValueError, "version"),
        ({"source_document": ""}, ValueError, "source document"),
        ({"source_section": ""}, ValueError, "source section"),
        ({"effective_from": cast(Any, datetime(2025, 1, 1))}, TypeError, "effective_from"),
        ({"effective_to": cast(Any, datetime(2025, 1, 1))}, TypeError, "effective_to"),
        ({"effective_to": date(2025, 6, 30)}, ValueError, "before"),
        ({"hours_per_pa": cast(Any, Decimal("4"))}, TypeError, "hours_per_pa"),
        ({"hours_per_pa": Hours.from_value("0")}, ValueError, "greater than zero"),
        ({"pa_cap": cast(Any, Decimal("10"))}, TypeError, "pa_cap"),
        ({"pa_cap": ProgrammedActivities.from_value("0")}, ValueError, "greater than zero"),
        ({"common_components": cast(Any, [])}, TypeError, "common_components"),
        ({"common_components": cast(Any, ("bad",))}, TypeError, "common_components"),
        ({"appointment_eras": ()}, ValueError, "at least one"),
        ({"appointment_eras": cast(Any, ("bad",))}, TypeError, "appointment_eras"),
    ],
)
def test_policy_version_field_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        replace(HR78_V3_CONSULTANT_POLICY, **changes)


def test_policy_rejects_overlapping_eras_and_duplicate_component_ids() -> None:
    first_era = _era(appointment_to=date(2025, 1, 1))
    overlapping_era = _era(
        rule_id=RuleId("test.era.second"),
        appointment_from=date(2025, 1, 1),
    )
    with pytest.raises(ValueError, match="overlapping"):
        replace(
            HR78_V3_CONSULTANT_POLICY,
            appointment_eras=(first_era, overlapping_era),
        )

    duplicate = _component(rule_id=RuleId("entitlement.stat-days"))
    with pytest.raises(ValueError, match="component IDs"):
        replace(
            HR78_V3_CONSULTANT_POLICY,
            appointment_eras=(_era(tiers=(_tier(components=(duplicate,)),)),),
        )


def test_policy_resolution_rejects_invalid_inputs_and_unmatched_eras() -> None:
    with pytest.raises(TypeError, match="Calculation date"):
        HR78_V3_CONSULTANT_POLICY.applies_on(cast(Any, datetime(2025, 7, 1)))
    with pytest.raises(ValueError, match="does not apply"):
        HR78_V3_CONSULTANT_POLICY.resolve(
            calculation_date=date(2025, 6, 30),
            consultant_appointment_date=date(2010, 1, 1),
            completed_service_years=7,
            contracted_pas=ProgrammedActivities.from_value("10"),
        )
    with pytest.raises(TypeError, match="contracted_pas"):
        HR78_V3_CONSULTANT_POLICY.resolve(
            calculation_date=POLICY_DATE,
            consultant_appointment_date=date(2010, 1, 1),
            completed_service_years=7,
            contracted_pas=cast(Any, Decimal("10")),
        )

    modern_only = replace(
        HR78_V3_CONSULTANT_POLICY,
        appointment_eras=(HR78_V3_CONSULTANT_POLICY.appointment_eras[-1],),
    )
    with pytest.raises(ValueError, match="exactly one"):
        modern_only.resolve(
            calculation_date=POLICY_DATE,
            consultant_appointment_date=date(2000, 1, 1),
            completed_service_years=7,
            contracted_pas=ProgrammedActivities.from_value("10"),
        )


def test_catalogue_supports_adjacent_versions_and_rejects_gaps() -> None:
    first = replace(
        HR78_V3_CONSULTANT_POLICY,
        version="first",
        effective_to=date(2025, 12, 31),
    )
    second = replace(
        HR78_V3_CONSULTANT_POLICY,
        version="second",
        effective_from=date(2026, 1, 1),
    )
    catalogue = EntitlementPolicyCatalogue((first, second))

    assert catalogue.version_on(date(2025, 12, 31)) is first
    assert catalogue.version_on(date(2026, 1, 1)) is second
    with pytest.raises(LookupError, match="exactly one"):
        catalogue.version_on(date(2025, 6, 30))


def test_catalogue_validation_rejects_malformed_version_sets() -> None:
    first = replace(
        HR78_V3_CONSULTANT_POLICY,
        version="first",
        effective_to=date(2025, 12, 31),
    )
    second = replace(
        HR78_V3_CONSULTANT_POLICY,
        version="second",
        effective_from=date(2026, 1, 1),
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        EntitlementPolicyCatalogue(())
    with pytest.raises(TypeError, match="instances"):
        EntitlementPolicyCatalogue(cast(Any, ("bad",)))
    with pytest.raises(ValueError, match="ordered"):
        EntitlementPolicyCatalogue((second, first))
    with pytest.raises(ValueError, match="overlapping"):
        EntitlementPolicyCatalogue((first, HR78_V3_CONSULTANT_POLICY))


def test_catalogue_versions_must_be_a_tuple() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        EntitlementPolicyCatalogue(cast(Any, []))


def test_policy_type_is_exported_for_future_persistence_code() -> None:
    """Keep the public package interface stable for later API and database work."""

    assert isinstance(HR78_V3_CONSULTANT_POLICY, EntitlementPolicyVersion)

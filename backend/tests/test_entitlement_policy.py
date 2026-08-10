"""Policy examples and the small set of invariants calculations rely on."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from domain import Hours, ProgrammedActivities, RuleId
from entitlement_policy import (
    DEFAULT_ENTITLEMENT_POLICIES,
    HR78_V3_CONSULTANT_POLICY,
    AppointmentEra,
    EntitlementComponent,
    EntitlementComponentKind,
    EntitlementPolicyCatalogue,
    EntitlementPolicyVersion,
    ServiceTier,
)

POLICY_DATE = date(2025, 7, 1)


def resolve(appointment: date, service_years: int, pas: str = "10") -> Hours:
    result = HR78_V3_CONSULTANT_POLICY.resolve(
        calculation_date=POLICY_DATE,
        consultant_appointment_date=appointment,
        completed_service_years=service_years,
        contracted_pas=ProgrammedActivities.from_value(pas),
    )
    return result.value.annual_hours


@pytest.mark.parametrize(
    ("appointment", "service_years", "hours"),
    [
        (date(2004, 3, 31), 20, "272"),
        (date(2004, 4, 1), 6, "272"),
        (date(2004, 4, 1), 7, "280"),
        (date(2005, 3, 31), 7, "280"),
        (date(2005, 4, 1), 6, "272"),
        (date(2005, 4, 1), 7, "288"),
    ],
)
def test_hr78_appointment_and_service_boundaries(
    appointment: date, service_years: int, hours: str
) -> None:
    assert resolve(appointment, service_years) == Hours.from_value(hours)


@pytest.mark.parametrize(
    ("pas", "factor", "hours"),
    [
        ("0", "0", "0"),
        ("6", "0.6", "172.8"),
        ("8.47", "0.847", "243.936"),
        ("10", "1", "288"),
        ("12", "1", "288"),
    ],
)
def test_pa_proration_is_exact_and_capped(pas: str, factor: str, hours: str) -> None:
    result = HR78_V3_CONSULTANT_POLICY.resolve(
        calculation_date=POLICY_DATE,
        consultant_appointment_date=date(2010, 1, 1),
        completed_service_years=7,
        contracted_pas=ProgrammedActivities.from_value(pas),
    )
    assert result.value.proration_factor == Decimal(factor)
    assert result.value.annual_hours == Hours.from_value(hours)


def test_resolution_explains_components_and_rule_choices() -> None:
    result = HR78_V3_CONSULTANT_POLICY.resolve(
        calculation_date=POLICY_DATE,
        consultant_appointment_date=date(2010, 1, 1),
        completed_service_years=7,
        contracted_pas=ProgrammedActivities.from_value("8.47"),
    )
    components = {item.component.kind: item.adjusted_hours for item in result.value.components}
    assert components == {
        EntitlementComponentKind.STATUTORY: Hours.from_value("13.552"),
        EntitlementComponentKind.LOCAL: Hours.from_value("13.552"),
        EntitlementComponentKind.CORE: Hours.from_value("203.28"),
        EntitlementComponentKind.SENIORITY: Hours.from_value("13.552"),
    }
    assert len(result.trace) == 3
    assert result.trace[-1].context["proration_factor"] == "0.847"


def test_default_catalogue_and_service_milestone() -> None:
    policy = DEFAULT_ENTITLEMENT_POLICIES.version_on(POLICY_DATE)
    modern_era = policy.appointment_eras[-1]
    assert policy is HR78_V3_CONSULTANT_POLICY
    assert modern_era.service_milestones == (7,)
    assert modern_era.tier_for(6).minimum_completed_years == 0
    assert modern_era.tier_for(7).minimum_completed_years == 7


def test_exact_pa_input_rejects_invalid_values() -> None:
    assert str(ProgrammedActivities.from_value("8.470")) == "8.470"
    for value in ("not-a-number", Decimal("NaN"), "-0.1"):
        with pytest.raises(ValueError):
            ProgrammedActivities.from_value(value)


def test_policy_configuration_keeps_material_invariants() -> None:
    component = EntitlementComponent(
        RuleId("test.component"), "Test", EntitlementComponentKind.CORE, Hours.from_value("8")
    )
    tier = ServiceTier(RuleId("test.tier"), 0, (component,))
    era = AppointmentEra(RuleId("test.era"), "Test", None, None, (tier,))

    with pytest.raises(ValueError, match="negative"):
        replace(component, full_time_hours=Hours.from_value("-1"))
    with pytest.raises(ValueError, match="zero years"):
        replace(era, service_tiers=(replace(tier, minimum_completed_years=1),))
    with pytest.raises(ValueError, match="overlapping"):
        replace(HR78_V3_CONSULTANT_POLICY, appointment_eras=(era, era))
    with pytest.raises(ValueError, match="ordered"):
        EntitlementPolicyCatalogue(
            tuple(
                reversed(
                    (
                        HR78_V3_CONSULTANT_POLICY,
                        replace(
                            HR78_V3_CONSULTANT_POLICY,
                            version="future",
                            effective_from=date(2030, 1, 1),
                        ),
                    )
                )
            )
        )


def test_policy_lookup_requires_one_matching_version() -> None:
    with pytest.raises(LookupError):
        DEFAULT_ENTITLEMENT_POLICIES.version_on(date(2020, 1, 1))
    assert isinstance(HR78_V3_CONSULTANT_POLICY, EntitlementPolicyVersion)

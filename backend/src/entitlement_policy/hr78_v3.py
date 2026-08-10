"""Consultant entitlement data encoded from HR78 version 3, section 7.4."""

from datetime import date

from domain import Hours, ProgrammedActivities, RuleId

from .models import (
    AppointmentEra,
    EntitlementComponent,
    EntitlementComponentKind,
    ServiceTier,
)
from .policy import EntitlementPolicyCatalogue, EntitlementPolicyVersion

STATUTORY_DAYS = EntitlementComponent(
    rule_id=RuleId("entitlement.stat-days"),
    label="Statutory Days",
    kind=EntitlementComponentKind.STATUTORY,
    full_time_hours=Hours.from_value("16"),
)
LOCALLY_AGREED_DAYS = EntitlementComponent(
    rule_id=RuleId("entitlement.local-days"),
    label="Hospital R&R",
    kind=EntitlementComponentKind.LOCAL,
    full_time_hours=Hours.from_value("16"),
)
CORE_30_DAYS = EntitlementComponent(
    rule_id=RuleId("entitlement.core"),
    label="Basic Leave",
    kind=EntitlementComponentKind.CORE,
    full_time_hours=Hours.from_value("240"),
)
SENIORITY_ONE_DAY = EntitlementComponent(
    rule_id=RuleId("entitlement.seniority"),
    label="Seniority",
    kind=EntitlementComponentKind.SENIORITY,
    full_time_hours=Hours.from_value("8"),
)
SENIORITY_TWO_DAYS = EntitlementComponent(
    rule_id=RuleId("entitlement.seniority"),
    label="Seniority",
    kind=EntitlementComponentKind.SENIORITY,
    full_time_hours=Hours.from_value("16"),
)


HR78_V3_CONSULTANT_POLICY = EntitlementPolicyVersion(
    version="hr78-v3-2025-07",
    source_document="HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf",
    source_section="7.4 Consultants Annual Leave Entitlements",
    # The PDF gives only the ratification month. Keep this working date visible
    # beside the policy data until the Trust owner confirms the operational day.
    effective_from=date(2025, 7, 1),
    effective_to=None,
    hours_per_pa=Hours.from_value("4"),
    pa_cap=ProgrammedActivities.from_value("10"),
    common_components=(STATUTORY_DAYS, LOCALLY_AGREED_DAYS),
    appointment_eras=(
        AppointmentEra(
            rule_id=RuleId("entitlement.era.pre-2004"),
            label="Appointed up to 31 March 2004",
            appointment_from=None,
            appointment_to=date(2004, 3, 31),
            service_tiers=(
                ServiceTier(
                    rule_id=RuleId("entitlement.tier.pre-2004"),
                    minimum_completed_years=0,
                    components=(CORE_30_DAYS,),
                ),
            ),
        ),
        AppointmentEra(
            rule_id=RuleId("entitlement.era.2004-2005"),
            label="Appointed from 1 April 2004 to 31 March 2005",
            appointment_from=date(2004, 4, 1),
            appointment_to=date(2005, 3, 31),
            service_tiers=(
                ServiceTier(
                    rule_id=RuleId("entitlement.tier.2004-2005.under-7"),
                    minimum_completed_years=0,
                    components=(CORE_30_DAYS,),
                ),
                ServiceTier(
                    rule_id=RuleId("entitlement.tier.2004-2005.7-plus"),
                    minimum_completed_years=7,
                    components=(CORE_30_DAYS, SENIORITY_ONE_DAY),
                ),
            ),
        ),
        AppointmentEra(
            rule_id=RuleId("entitlement.era.from-2005"),
            label="Appointed from 1 April 2005",
            appointment_from=date(2005, 4, 1),
            appointment_to=None,
            service_tiers=(
                ServiceTier(
                    rule_id=RuleId("entitlement.tier.from-2005.under-7"),
                    minimum_completed_years=0,
                    components=(CORE_30_DAYS,),
                ),
                ServiceTier(
                    rule_id=RuleId("entitlement.tier.from-2005.7-plus"),
                    minimum_completed_years=7,
                    components=(CORE_30_DAYS, SENIORITY_TWO_DAYS),
                ),
            ),
        ),
    ),
)

DEFAULT_ENTITLEMENT_POLICIES = EntitlementPolicyCatalogue(versions=(HR78_V3_CONSULTANT_POLICY,))

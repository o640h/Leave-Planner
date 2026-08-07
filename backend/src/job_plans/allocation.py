"""Allocation of leave hours using a job plan's contracted PA split."""

from domain import ZERO_HOURS, ActivityType, Hours

from .models import JobPlanCycle


def allocate_hours_by_pa(
    hours: Hours,
    cycle: JobPlanCycle,
) -> tuple[Hours, Hours, Hours]:
    """Split hours into DCC, SPA, and Other using contracted PAs."""

    if not isinstance(hours, Hours):
        raise TypeError("hours must be an Hours instance")

    if not isinstance(cycle, JobPlanCycle):
        raise TypeError("cycle must be a JobPlanCycle")

    allocations = (
        (ActivityType.DCC, cycle.dcc_pas.value),
        (ActivityType.SPA, cycle.spa_pas.value),
        (ActivityType.OTHER, cycle.other_pas.value),
    )
    non_zero_activities = tuple(
        activity_type
        for activity_type, programmed_activities in allocations
        if programmed_activities > 0
    )

    if not non_zero_activities:
        return ZERO_HOURS, ZERO_HOURS, ZERO_HOURS

    results = {
        ActivityType.DCC: ZERO_HOURS,
        ActivityType.SPA: ZERO_HOURS,
        ActivityType.OTHER: ZERO_HOURS,
    }
    allocated = ZERO_HOURS

    for activity_type in non_zero_activities[:-1]:
        amount = hours.scale(cycle.activity_proportion(activity_type))
        results[activity_type] = amount
        allocated += amount

    # Give any tiny Decimal division remainder to the final activity.
    # This ensures that the three results add back to the source hours.
    final_activity = non_zero_activities[-1]
    results[final_activity] = hours - allocated

    return (
        results[ActivityType.DCC],
        results[ActivityType.SPA],
        results[ActivityType.OTHER],
    )

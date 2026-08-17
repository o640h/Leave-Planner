import type { LeaveYear } from '../leaveYears/types'
import { addNonNegativeDecimals, formatDecimal } from '../system/decimal'

export type JobPlanDayInput = {
  cycle_week: number
  weekday: number
  dcc_hours: string
  spa_hours: string
  other_hours: string
}

export type JobPlanInput = {
  effective_from: string
  effective_until: string
  cycle_anchor_date: string | null
  week_count: number
  contracted_pas: string
  dcc_pas: string
  spa_pas: string
  other_pas: string
  hours_per_pa: string
  reconciliation_override_reason: string | null
  days: JobPlanDayInput[]
}

export type JobPlan = JobPlanInput & {
  id: number
  leave_year_id: number
}

export type JobPlanPreview = JobPlanInput & {
  allocated_pas: string
  reconciliation_variance: string
  is_reconciled: boolean
  average_visible_hours: string
  average_dcc_hours: string
  average_spa_hours: string
  average_other_hours: string
  scheduled_average_pas: string
  warning: string | null
}

export type JobPlanUpdateImpact = {
  affected_bookings: number
  affected_booking_days: number
  current_dcc_hours: string
  current_spa_hours: string
  current_total_hours: string
  updated_dcc_hours: string
  updated_spa_hours: string
  updated_total_hours: string
  difference_hours: string
  requires_confirmation: boolean
}

function addOneDay(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  const result = new Date(Date.UTC(year, month - 1, day))

  result.setUTCDate(result.getUTCDate() + 1)
  return result.toISOString().slice(0, 10)
}

export function cycleDays(weekCount: number, existing: JobPlanDayInput[] = []): JobPlanDayInput[] {
  return Array.from({ length: weekCount }, (_, weekIndex) =>
    Array.from({ length: 7 }, (_, weekday) => {
      const cycleWeek = weekIndex + 1
      const current = existing.find(
        (day) => day.cycle_week === cycleWeek && day.weekday === weekday,
      )

      return current
        ? {
            ...current,
            dcc_hours: formatDecimal(current.dcc_hours, 2),
            spa_hours: formatDecimal(current.spa_hours, 2),
            other_hours: formatDecimal(current.other_hours, 2),
          }
        : {
            cycle_week: cycleWeek,
            weekday,
            dcc_hours: '0',
            spa_hours: '0',
            other_hours: '0',
          }
    }),
  ).flat()
}

export function emptyJobPlanInput(leaveYear: LeaveYear): JobPlanInput {
  return {
    effective_from: leaveYear.start_date,
    effective_until: addOneDay(leaveYear.end_date),
    cycle_anchor_date: null,
    week_count: 1,
    contracted_pas: '0',
    dcc_pas: '0',
    spa_pas: '0',
    other_pas: '0',
    hours_per_pa: '4',
    reconciliation_override_reason: null,
    days: cycleDays(1),
  }
}

export function editableJobPlan(jobPlan: JobPlan): JobPlanInput {
  return {
    effective_from: jobPlan.effective_from,
    effective_until: jobPlan.effective_until,
    // A one-week pattern does not need an anchor. Keeping its old generated
    // anchor after moving Effective From can make an invisible stale date fail
    // backend validation.
    cycle_anchor_date: jobPlan.week_count > 1 ? jobPlan.cycle_anchor_date : null,
    week_count: jobPlan.week_count,
    contracted_pas: addNonNegativeDecimals(jobPlan.dcc_pas, jobPlan.spa_pas),
    dcc_pas: formatDecimal(jobPlan.dcc_pas, 2),
    spa_pas: formatDecimal(jobPlan.spa_pas, 2),
    other_pas: '0',
    hours_per_pa: formatDecimal(jobPlan.hours_per_pa, 2),
    reconciliation_override_reason: jobPlan.reconciliation_override_reason,
    days: cycleDays(jobPlan.week_count, jobPlan.days),
  }
}

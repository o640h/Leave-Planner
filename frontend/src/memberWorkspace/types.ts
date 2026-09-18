import type { ActivityHours, LeaveWarning } from '../planning/types'

export type MemberLeaveYear = {
  id: number
  start_date: string
  end_date: string
  employment_start: string | null
  employment_end: string | null
}

export type MemberJobPlanDay = {
  cycle_week: number
  weekday: number
  dcc_hours: string
  spa_hours: string
  other_hours: string
}

export type MemberJobPlan = {
  effective_from: string
  effective_until: string
  cycle_anchor_date: string | null
  week_count: number
  contracted_pas: string
  dcc_pas: string
  spa_pas: string
  other_pas: string
  hours_per_pa: string
  days: MemberJobPlanDay[]
}

type EntitlementAmounts = ActivityHours

type EntitlementRecommendation = {
  inputs: {
    seven_years_or_more: boolean
    policy_versions: string[]
    public_holiday_source: string
    public_holiday_source_date: string
  }
  base_entitlement: EntitlementAmounts
  public_holiday_entitlement: EntitlementAmounts
  recommended_entitlement: EntitlementAmounts
  components: Array<{
    label: string
    kind: string
    full_time_hours: string
    prorated_hours: string
  }>
  trace: Array<{
    description: string
    amount: string | null
    effective_date: string | null
  }>
}

type AppliedEntitlement = {
  mode: 'calculated' | 'manual'
  entitlement: EntitlementAmounts
  reason: string | null
  updated_at: string
}

export type MemberBalancePosition = {
  available: ActivityHours
  used: ActivityHours
  remaining: ActivityHours
}

export type MemberYearSummary = {
  leave_year: MemberLeaveYear
  job_plans: MemberJobPlan[]
  entitlement: {
    recommendation: EntitlementRecommendation | null
    application: AppliedEntitlement | null
  }
  carry_forward: {
    dcc_hours: string
    spa_hours: string
    total_hours: string
  }
  allocation_source: 'recommendation' | 'applied' | null
  job_plan_periods: Array<{
    effective_from: string
    effective_until: string
    calendar_days: number
    contracted_pas: string
    dcc_pas: string
    spa_pas: string
    standard_dcc_hours: string
    standard_spa_hours: string
    gross_entitlement_hours: string
    dcc_entitlement_hours: string
    spa_entitlement_hours: string
  }>
  holidays: Array<{
    holiday_date: string
    name: string
    basis: string
    entitlement_hours: string
    dcc_deduction_hours: string
    spa_deduction_hours: string
  }>
  bookings: Array<{
    start_date: string
    end_date: string
    state: string
    note: string | null
    days: Array<{
      leave_date: string
      deduction: ActivityHours
      override_reason: string | null
      public_holiday_name: string | null
    }>
  }>
  balances: {
    requested: MemberBalancePosition | null
    approved: MemberBalancePosition | null
  }
  weekday_counts: Record<'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday', number>
  warnings: LeaveWarning[]
}

export type MemberWorkspaceData = {
  state: 'linked' | 'waiting'
  workspace_name: string
  consultant: { name: string; post_title: string | null } | null
  leave_years: MemberLeaveYear[]
  selected_year: MemberYearSummary | null
}

export type MemberWallchart = {
  month: string
  holidays: Array<{ holiday_date: string; name: string }>
  people: Array<{
    display_name: string
    leave_dates: Array<{ leave_date: string; state: 'requested' | 'approved' }>
  }>
}

import type { EntitlementWorkspace } from '../annualEntitlement/types'
import type { CarryForward } from '../carryForward/types'
import type { Consultant } from '../consultants/types'
import type { JobPlan } from '../jobPlans/types'
import type { ActivityHours, LeaveWarning, PlanningWorkspace } from '../planning/types'
import type { LeaveYear } from '../leaveYears/types'

export type JobPlanPeriodSummary = {
  job_plan_id: number
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
}

export type BalancePosition = {
  available: ActivityHours
  used: ActivityHours
  remaining: ActivityHours
}

export type BalanceViews = {
  requested: BalancePosition | null
  approved: BalancePosition | null
}

export type WeekdayCounts = {
  monday: number
  tuesday: number
  wednesday: number
  thursday: number
  friday: number
}

export type AuditEvent = {
  id: number
  actor_label: string
  entity_type: string
  action: string
  recorded_at: string
  details: Record<string, unknown>
}

export type LeaveLogEntry = {
  key: string
  start_date: string
  end_date: string
  description: string
  state: string
  amounts: ActivityHours
}

export type ConsultantYearSummary = {
  consultant: Consultant
  leave_year: LeaveYear
  job_plans: JobPlan[]
  entitlement: EntitlementWorkspace
  carry_forward: CarryForward
  allocation_source: 'recommendation' | 'applied' | null
  job_plan_periods: JobPlanPeriodSummary[]
  planning: PlanningWorkspace
  leave_log: LeaveLogEntry[]
  balances: BalanceViews
  weekday_counts: WeekdayCounts
  warnings: LeaveWarning[]
  audit_events: AuditEvent[]
}

import type { HolidayOccurrence } from '../publicHolidays/types'

export type LeaveState = 'planned' | 'approved' | 'taken' | 'cancelled'

export type ActivityHours = {
  dcc_hours: string
  spa_hours: string
  other_hours: string
  total_hours: string
}

export type LeaveDay = {
  leave_date: string
  job_plan_id: number | null
  contracted_pas: string | null
  deduction_factor: string | null
  standard: ActivityHours
  deduction: ActivityHours
  calculated_deduction: ActivityHours
  override_reason: string | null
  public_holiday_name: string | null
}

export type Balance = {
  opening: ActivityHours
  carry_forward: ActivityHours
  public_holidays: ActivityHours
  bookings: ActivityHours
  remaining: ActivityHours
}

export type LeaveWarning = { code: string; message: string; severity: string }

export type DailyOverrideInput = {
  leave_date: string
  dcc_hours: string | null
  spa_hours: string | null
  other_hours: string | null
  reason: string | null
}

export type LeaveBookingInput = {
  start_date: string
  end_date: string
  state: LeaveState
  note: string | null
  overrides: DailyOverrideInput[]
}

export type LeavePreview = {
  days: LeaveDay[]
  projected: Balance | null
  confirmed: Balance | null
  actual: Balance | null
  warnings: LeaveWarning[]
}

export type LeaveBooking = {
  id: number
  leave_year_id: number
  start_date: string
  end_date: string
  state: LeaveState
  note: string | null
  days: LeaveDay[]
  created_at: string
  updated_at: string
}

export type PlanningWorkspace = {
  leave_year_id: number
  start_date: string
  end_date: string
  holidays: HolidayOccurrence[]
  bookings: LeaveBooking[]
  projected: Balance | null
  confirmed: Balance | null
  actual: Balance | null
  warnings: LeaveWarning[]
}

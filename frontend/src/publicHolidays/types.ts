export type HolidayCorrectionAction = 'add_or_replace' | 'remove'
export type HolidayTreatmentBasis = 'standard' | 'qualifying_on_call'

export type Holiday = { holiday_date: string; name: string; notes: string }
export type HolidayCorrection = {
  id: number
  holiday_date: string
  action: HolidayCorrectionAction
  replacement_name: string | null
  reason: string
  created_at: string
}
export type HolidaySettings = {
  source: string
  source_date: string
  holidays: Holiday[]
  corrections: HolidayCorrection[]
}
export type HolidayOccurrence = Holiday & {
  basis: HolidayTreatmentBasis
  treatment_note: string | null
  worked_date: string | null
  contracted_pas: string
  deduction_factor: string
  entitlement_hours: string
  dcc_entitlement_hours: string
  spa_entitlement_hours: string
  dcc_deduction_hours: string
  spa_deduction_hours: string
}
export type LeaveYearHolidays = {
  source: string
  source_date: string
  entitlement_hours: string
  deduction_hours: string
  occurrences: HolidayOccurrence[]
}

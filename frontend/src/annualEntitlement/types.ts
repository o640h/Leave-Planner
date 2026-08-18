import { formatDecimal } from '../system/decimal'

export type EntitlementMode = 'calculated' | 'manual'

export type EntitlementAmounts = {
  dcc_hours: string
  spa_hours: string
  other_hours: string
  total_hours: string
}

export type EntitlementInputs = {
  seven_years_or_more: boolean
  policy_versions: string[]
  public_holiday_source: string
  public_holiday_source_date: string
}

export type EntitlementTraceStep = {
  rule_id: string
  description: string
  amount: string | null
  effective_date: string | null
  context: Record<string, string>
}

export type EntitlementComponentSummary = {
  label: string
  kind: string
  full_time_hours: string
  prorated_hours: string
}

export type EntitlementRecommendation = {
  inputs: EntitlementInputs
  base_entitlement: EntitlementAmounts
  public_holiday_entitlement: EntitlementAmounts
  recommended_entitlement: EntitlementAmounts
  components: EntitlementComponentSummary[]
  trace: EntitlementTraceStep[]
}

export type EntitlementRecommendationRead = EntitlementRecommendation & {
  id: number
  created_at: string
}

export type AppliedEntitlement = {
  id: number
  leave_year_id: number
  recommendation_id: number | null
  mode: EntitlementMode
  entitlement: EntitlementAmounts
  reason: string | null
  updated_at: string
}

export type EntitlementWorkspace = {
  recommendation: EntitlementRecommendationRead | null
  application: AppliedEntitlement | null
}

export type EntitlementApplyInput = {
  mode: EntitlementMode
  seven_years_or_more?: boolean
  dcc_hours?: string
  spa_hours?: string
  other_hours: string
  reason?: string | null
}

export function displayAmounts(amounts: EntitlementAmounts): EntitlementAmounts {
  return {
    dcc_hours: formatDecimal(amounts.dcc_hours),
    spa_hours: formatDecimal(amounts.spa_hours),
    other_hours: formatDecimal(amounts.other_hours),
    total_hours: formatDecimal(amounts.total_hours),
  }
}

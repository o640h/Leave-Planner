import { apiRequest } from '../api/client'
import type {
  EntitlementApplyInput,
  EntitlementRecommendation,
  EntitlementWorkspace,
} from './types'

function entitlementPath(consultantId: number, leaveYearId: number): string {
  return `/api/consultants/${consultantId}` + `/leave-years/${leaveYearId}/entitlement`
}

export function getEntitlement(
  consultantId: number,
  leaveYearId: number,
): Promise<EntitlementWorkspace> {
  return apiRequest<EntitlementWorkspace>(entitlementPath(consultantId, leaveYearId))
}

export function previewEntitlement(
  consultantId: number,
  leaveYearId: number,
  sevenYearsOrMore: boolean,
): Promise<EntitlementRecommendation> {
  const query = new URLSearchParams({
    seven_years_or_more: String(sevenYearsOrMore),
  })

  return apiRequest<EntitlementRecommendation>(
    `${entitlementPath(consultantId, leaveYearId)}/preview?${query}`,
    { method: 'POST' },
  )
}

export function applyEntitlement(
  consultantId: number,
  leaveYearId: number,
  details: EntitlementApplyInput,
): Promise<EntitlementWorkspace> {
  return apiRequest<EntitlementWorkspace>(entitlementPath(consultantId, leaveYearId), {
    method: 'PUT',
    body: JSON.stringify(details),
  })
}

export function refreshEntitlement(
  consultantId: number,
  leaveYearId: number,
): Promise<EntitlementWorkspace> {
  return apiRequest<EntitlementWorkspace>(`${entitlementPath(consultantId, leaveYearId)}/refresh`, {
    method: 'POST',
  })
}

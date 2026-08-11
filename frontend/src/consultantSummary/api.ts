import { apiRequest } from '../api/client'
import type { ConsultantYearSummary } from './types'

export function getConsultantYearSummary(
  consultantId: number,
  leaveYearId: number,
): Promise<ConsultantYearSummary> {
  return apiRequest(`/api/consultants/${consultantId}/leave-years/${leaveYearId}/summary`)
}

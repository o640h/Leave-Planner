import { apiFileRequest, apiRequest } from '../api/client'
import type { ConsultantYearSummary } from './types'

export function getConsultantYearSummary(
  consultantId: number,
  leaveYearId: number,
): Promise<ConsultantYearSummary> {
  return apiRequest(`/api/consultants/${consultantId}/leave-years/${leaveYearId}/summary`)
}

export function getLeaveLogPdf(consultantId: number, leaveYearId: number) {
  return apiFileRequest(`/api/consultants/${consultantId}/leave-years/${leaveYearId}/leave-log.pdf`)
}

import { apiRequest } from '../api/client'
import type { LeaveYear, LeaveYearInput } from './types'

const leaveYearPath = (consultantId: number) => `/api/consultants/${consultantId}/leave-years`

export function listLeaveYears(consultantId: number): Promise<LeaveYear[]> {
  return apiRequest<LeaveYear[]>(leaveYearPath(consultantId))
}

export function createLeaveYear(consultantId: number, details: LeaveYearInput): Promise<LeaveYear> {
  return apiRequest<LeaveYear>(leaveYearPath(consultantId), {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function updateLeaveYear(
  consultantId: number,
  leaveYearId: number,
  details: LeaveYearInput,
): Promise<LeaveYear> {
  return apiRequest<LeaveYear>(`${leaveYearPath(consultantId)}/${leaveYearId}`, {
    method: 'PUT',
    body: JSON.stringify(details),
  })
}

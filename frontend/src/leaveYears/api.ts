import { apiRequest } from '../api/client'
import type { RemovalImpact, RemovalResult } from '../system/removal'
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

export function leaveYearRemovalImpact(
  consultantId: number,
  leaveYearId: number,
): Promise<RemovalImpact> {
  return apiRequest<RemovalImpact>(`${leaveYearPath(consultantId)}/${leaveYearId}/removal-impact`)
}

export function removeLeaveYear(
  consultantId: number,
  leaveYearId: number,
  confirmation: string,
): Promise<RemovalResult> {
  return apiRequest<RemovalResult>(`${leaveYearPath(consultantId)}/${leaveYearId}/remove`, {
    method: 'POST',
    body: JSON.stringify({ confirmation }),
  })
}

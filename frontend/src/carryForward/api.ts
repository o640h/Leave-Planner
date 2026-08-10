import { apiRequest } from '../api/client'
import type { CarryForward } from './types'

function path(consultantId: number, leaveYearId: number): string {
  return `/api/consultants/${consultantId}/leave-years/${leaveYearId}/carry-forward`
}

export function getCarryForward(consultantId: number, leaveYearId: number): Promise<CarryForward> {
  return apiRequest(path(consultantId, leaveYearId))
}

export function setCarryForward(
  consultantId: number,
  leaveYearId: number,
  hours: string,
): Promise<CarryForward> {
  return apiRequest(path(consultantId, leaveYearId), {
    method: 'PUT',
    body: JSON.stringify({ hours }),
  })
}

import { apiRequest } from '../api/client'
import type { LeaveBookingInput, LeavePreview, PlanningWorkspace } from './types'

const root = (consultantId: number, leaveYearId: number) =>
  `/api/consultants/${consultantId}/leave-years/${leaveYearId}`

export function getPlanning(consultantId: number, leaveYearId: number): Promise<PlanningWorkspace> {
  return apiRequest<PlanningWorkspace>(`${root(consultantId, leaveYearId)}/planning`)
}

export function previewBooking(
  consultantId: number,
  leaveYearId: number,
  details: LeaveBookingInput,
  bookingId?: number,
): Promise<LeavePreview> {
  const path = bookingId
    ? `${root(consultantId, leaveYearId)}/bookings/${bookingId}/preview`
    : `${root(consultantId, leaveYearId)}/bookings/preview`
  return apiRequest<LeavePreview>(path, { method: 'POST', body: JSON.stringify(details) })
}

export function saveBooking(
  consultantId: number,
  leaveYearId: number,
  details: LeaveBookingInput,
  bookingId?: number,
): Promise<PlanningWorkspace> {
  return apiRequest<PlanningWorkspace>(
    bookingId
      ? `${root(consultantId, leaveYearId)}/bookings/${bookingId}`
      : `${root(consultantId, leaveYearId)}/bookings`,
    { method: bookingId ? 'PUT' : 'POST', body: JSON.stringify(details) },
  )
}

export function removeBooking(
  consultantId: number,
  leaveYearId: number,
  bookingId: number,
): Promise<PlanningWorkspace> {
  return apiRequest<PlanningWorkspace>(`${root(consultantId, leaveYearId)}/bookings/${bookingId}`, {
    method: 'DELETE',
  })
}

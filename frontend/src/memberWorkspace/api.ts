import { apiRequest } from '../api/client'
import type { LeavePreview } from '../planning/types'
import type { MemberWallchart, MemberWorkspaceData } from './types'

export function getMemberWorkspace(leaveYearId?: number): Promise<MemberWorkspaceData> {
  const query = leaveYearId === undefined ? '' : `?leave_year_id=${leaveYearId}`
  return apiRequest<MemberWorkspaceData>(`/api/member/workspace${query}`)
}

export function getMemberWallchart(month: string): Promise<MemberWallchart> {
  return apiRequest<MemberWallchart>(`/api/member/wallchart?month=${month}-01`)
}

export type MemberLeaveRequestInput = {
  start_date: string
  end_date: string
  note: string | null
}

const requestRoot = (leaveYearId: number) => `/api/member/leave-years/${leaveYearId}`

export function previewMemberLeaveRequest(
  leaveYearId: number,
  details: MemberLeaveRequestInput,
): Promise<LeavePreview> {
  return apiRequest(`${requestRoot(leaveYearId)}/requests/preview`, {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function submitMemberLeaveRequest(
  leaveYearId: number,
  details: MemberLeaveRequestInput,
): Promise<MemberWorkspaceData> {
  return apiRequest(`${requestRoot(leaveYearId)}/requests`, {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function cancelMemberLeaveRequest(
  leaveYearId: number,
  bookingId: number,
): Promise<MemberWorkspaceData> {
  return apiRequest(`${requestRoot(leaveYearId)}/bookings/${bookingId}/cancel`, {
    method: 'POST',
  })
}

export function requestMemberLeaveCancellation(
  leaveYearId: number,
  bookingId: number,
): Promise<MemberWorkspaceData> {
  return apiRequest(`${requestRoot(leaveYearId)}/bookings/${bookingId}/request-cancellation`, {
    method: 'POST',
  })
}

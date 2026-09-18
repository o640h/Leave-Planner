import { apiRequest } from '../api/client'
import type { MemberWallchart, MemberWorkspaceData } from './types'

export function getMemberWorkspace(leaveYearId?: number): Promise<MemberWorkspaceData> {
  const query = leaveYearId === undefined ? '' : `?leave_year_id=${leaveYearId}`
  return apiRequest<MemberWorkspaceData>(`/api/member/workspace${query}`)
}

export function getMemberWallchart(month: string): Promise<MemberWallchart> {
  return apiRequest<MemberWallchart>(`/api/member/wallchart?month=${month}-01`)
}

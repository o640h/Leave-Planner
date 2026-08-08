import { apiRequest } from '../api/client'
import type { JobPlan, JobPlanInput, JobPlanPreview } from './types'

function jobPlanPath(consultantId: number, leaveYearId: number): string {
  return `/api/consultants/${consultantId}/leave-years/${leaveYearId}/job-plans`
}

export function listJobPlans(consultantId: number, leaveYearId: number): Promise<JobPlan[]> {
  return apiRequest<JobPlan[]>(jobPlanPath(consultantId, leaveYearId))
}

export function previewJobPlan(
  consultantId: number,
  leaveYearId: number,
  details: JobPlanInput,
): Promise<JobPlanPreview> {
  return apiRequest<JobPlanPreview>(`${jobPlanPath(consultantId, leaveYearId)}/preview`, {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function createJobPlan(
  consultantId: number,
  leaveYearId: number,
  details: JobPlanInput,
): Promise<JobPlan> {
  return apiRequest<JobPlan>(jobPlanPath(consultantId, leaveYearId), {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function updateJobPlan(
  consultantId: number,
  leaveYearId: number,
  jobPlanId: number,
  details: JobPlanInput,
): Promise<JobPlan> {
  return apiRequest<JobPlan>(`${jobPlanPath(consultantId, leaveYearId)}/${jobPlanId}`, {
    method: 'PUT',
    body: JSON.stringify(details),
  })
}

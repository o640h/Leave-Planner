import { apiRequest } from '../api/client'
import type { RemovalImpact, RemovalResult } from '../system/removal'
import type { JobPlan, JobPlanInput, JobPlanPreview, JobPlanUpdateImpact } from './types'

function jobPlanPath(consultantId: number, leaveYearId: number): string {
  return `/api/consultants/${consultantId}/leave-years/${leaveYearId}/job-plans`
}

function shiftIsoDate(value: string, days: number): string {
  const [year, month, day] = value.split('-').map(Number)
  const result = new Date(Date.UTC(year, month - 1, day))

  result.setUTCDate(result.getUTCDate() + days)
  return result.toISOString().slice(0, 10)
}

function toApiJobPlan(details: JobPlanInput): JobPlanInput {
  return {
    ...details,
    effective_until: shiftIsoDate(details.effective_until, 1),
  }
}

function fromApiJobPlan<T extends JobPlanInput>(details: T): T {
  return {
    ...details,
    effective_until: shiftIsoDate(details.effective_until, -1),
  }
}

export function listJobPlans(consultantId: number, leaveYearId: number): Promise<JobPlan[]> {
  return apiRequest<JobPlan[]>(jobPlanPath(consultantId, leaveYearId)).then((records) =>
    records.map((record) => fromApiJobPlan(record)),
  )
}

export function previewJobPlan(
  consultantId: number,
  leaveYearId: number,
  details: JobPlanInput,
): Promise<JobPlanPreview> {
  return apiRequest<JobPlanPreview>(`${jobPlanPath(consultantId, leaveYearId)}/preview`, {
    method: 'POST',
    body: JSON.stringify(toApiJobPlan(details)),
  }).then((preview) => fromApiJobPlan(preview))
}

export function createJobPlan(
  consultantId: number,
  leaveYearId: number,
  details: JobPlanInput,
): Promise<JobPlan> {
  return apiRequest<JobPlan>(jobPlanPath(consultantId, leaveYearId), {
    method: 'POST',
    body: JSON.stringify(toApiJobPlan(details)),
  }).then((record) => fromApiJobPlan(record))
}

export function updateJobPlan(
  consultantId: number,
  leaveYearId: number,
  jobPlanId: number,
  details: JobPlanInput,
  regenerateBookingDays = false,
): Promise<JobPlan> {
  const query = regenerateBookingDays ? '?regenerate_booking_days=true' : ''

  return apiRequest<JobPlan>(`${jobPlanPath(consultantId, leaveYearId)}/${jobPlanId}${query}`, {
    method: 'PUT',
    body: JSON.stringify(toApiJobPlan(details)),
  }).then((record) => fromApiJobPlan(record))
}

export function jobPlanUpdateImpact(
  consultantId: number,
  leaveYearId: number,
  jobPlanId: number,
  details: JobPlanInput,
): Promise<JobPlanUpdateImpact> {
  return apiRequest<JobPlanUpdateImpact>(
    `${jobPlanPath(consultantId, leaveYearId)}/${jobPlanId}/update-impact`,
    {
      method: 'POST',
      body: JSON.stringify(toApiJobPlan(details)),
    },
  )
}

export function jobPlanRemovalImpact(
  consultantId: number,
  leaveYearId: number,
  jobPlanId: number,
): Promise<RemovalImpact> {
  return apiRequest<RemovalImpact>(
    `${jobPlanPath(consultantId, leaveYearId)}/${jobPlanId}/removal-impact`,
  )
}

export function removeJobPlan(
  consultantId: number,
  leaveYearId: number,
  jobPlanId: number,
  confirmation: string,
): Promise<RemovalResult> {
  return apiRequest<RemovalResult>(
    `${jobPlanPath(consultantId, leaveYearId)}/${jobPlanId}/remove`,
    {
      method: 'POST',
      body: JSON.stringify({ confirmation }),
    },
  )
}

import { apiRequest } from '../api/client'
import type { RemovalImpact, RemovalResult } from '../system/removal'
import type { Consultant, ConsultantInput } from './types'

export function listConsultants(): Promise<Consultant[]> {
  return apiRequest<Consultant[]>('/api/consultants')
}

export function createConsultant(details: ConsultantInput): Promise<Consultant> {
  return apiRequest<Consultant>('/api/consultants', {
    method: 'POST',
    body: JSON.stringify(details),
  })
}

export function updateConsultant(
  consultantId: number,
  details: ConsultantInput,
): Promise<Consultant> {
  return apiRequest<Consultant>(`/api/consultants/${consultantId}`, {
    method: 'PUT',
    body: JSON.stringify(details),
  })
}

export function consultantArchiveImpact(consultantId: number): Promise<RemovalImpact> {
  return apiRequest<RemovalImpact>(`/api/consultants/${consultantId}/archive-impact`)
}

export function archiveConsultant(
  consultantId: number,
  confirmation: string,
): Promise<RemovalResult> {
  return apiRequest<RemovalResult>(`/api/consultants/${consultantId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ confirmation }),
  })
}

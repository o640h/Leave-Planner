import { apiRequest } from '../api/client'
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

import { apiFileRequest, apiRequest } from '../api/client'
import type { PolicyDocument } from './types'

export function getPolicyDocuments(): Promise<PolicyDocument[]> {
  return apiRequest('/api/policies')
}

export function getPolicyDocumentPdf(documentId: string) {
  return apiFileRequest(`/api/policies/${encodeURIComponent(documentId)}/download`)
}

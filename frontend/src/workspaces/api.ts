import { apiRequest } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'

export const selectWorkspace = (workspaceId: number) =>
  apiRequest<WorkspaceContext>('/api/workspaces/active', {
    method: 'POST',
    body: JSON.stringify({ workspace_id: workspaceId }),
  })

export const createWorkspace = (name: string) =>
  apiRequest<WorkspaceContext>('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })

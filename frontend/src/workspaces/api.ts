import { apiRequest } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import type { ManagedWorkspace, WorkspaceImpact, WorkspaceManagement } from './types'

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

export const listManagedWorkspaces = () => apiRequest<ManagedWorkspace[]>('/api/workspaces/managed')

export const getWorkspaceManagement = (workspaceId: number) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/management`)

export const renameWorkspace = (workspaceId: number, name: string) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/management`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  })

export const inviteWorkspacePerson = (
  workspaceId: number,
  email: string,
  role: 'admin' | 'member',
  linkedConsultantId: number | null,
) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/invitations`, {
    method: 'POST',
    body: JSON.stringify({
      email,
      role,
      linked_consultant_id: linkedConsultantId,
    }),
  })

export const resendWorkspaceInvitation = (workspaceId: number, invitationId: number) =>
  apiRequest<WorkspaceManagement>(
    `/api/workspaces/${workspaceId}/invitations/${invitationId}/resend`,
    { method: 'POST' },
  )

export const revokeWorkspaceInvitation = (workspaceId: number, invitationId: number) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/invitations/${invitationId}`, {
    method: 'DELETE',
  })

export const updateWorkspaceMember = (
  workspaceId: number,
  membershipId: number,
  role: 'admin' | 'member',
  linkedConsultantId: number | null,
) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/members/${membershipId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role, linked_consultant_id: linkedConsultantId }),
  })

export const removeWorkspaceMember = (workspaceId: number, membershipId: number) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/members/${membershipId}`, {
    method: 'DELETE',
  })

export const requestOwnershipTransfer = (workspaceId: number, targetMembershipId: number) =>
  apiRequest<WorkspaceManagement>(`/api/workspaces/${workspaceId}/ownership-transfers`, {
    method: 'POST',
    body: JSON.stringify({ target_membership_id: targetMembershipId }),
  })

export const acceptOwnershipTransfer = (workspaceId: number, transferId: number) =>
  apiRequest<WorkspaceManagement>(
    `/api/workspaces/${workspaceId}/ownership-transfers/${transferId}/accept`,
    { method: 'POST' },
  )

export const getWorkspaceImpact = (workspaceId: number) =>
  apiRequest<WorkspaceImpact>(`/api/workspaces/${workspaceId}/impact`)

export const deleteWorkspace = (workspaceId: number, confirmationName: string) =>
  apiRequest<WorkspaceContext>(`/api/workspaces/${workspaceId}`, {
    method: 'DELETE',
    body: JSON.stringify({ confirmation_name: confirmationName }),
  })

export const closeWorkspace = (workspaceId: number, confirmationName: string, password: string) =>
  apiRequest<WorkspaceContext>(`/api/workspaces/${workspaceId}/close`, {
    method: 'POST',
    body: JSON.stringify({ confirmation_name: confirmationName, password }),
  })

export const recoverWorkspace = (workspaceId: number, password: string) =>
  apiRequest<{ message: string }>(`/api/workspaces/${workspaceId}/recover`, {
    method: 'POST',
    body: JSON.stringify({ confirmation_name: 'recover', password }),
  })

export const acceptWorkspaceInvitation = (token: string) =>
  apiRequest<WorkspaceContext>('/api/workspaces/invitations/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })

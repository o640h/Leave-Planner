export type AuthenticatedUser = {
  public_id: string
  display_name: string
  display_email: string
}

export type WorkspaceMembership = {
  workspace_id: number
  workspace_name: string
  role: 'owner' | 'admin' | 'member'
  linked_consultant_id: number | null
}

export type WorkspaceContext = {
  state: 'active' | 'selection_required' | 'onboarding'
  active_workspace_id: number | null
  memberships: WorkspaceMembership[]
}

export type Session = {
  authenticated: boolean
  user: AuthenticatedUser | null
  workspace: WorkspaceContext | null
}

export type RegistrationMode = 'closed' | 'invitation_only' | 'open'

export type RegistrationConfiguration = {
  mode: RegistrationMode
}

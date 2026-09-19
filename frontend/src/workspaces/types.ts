export type ManagedWorkspace = {
  workspace_id: number
  workspace_name: string
  role: 'owner' | 'admin'
  status: 'active' | 'closed'
  closed_at: string | null
  purge_after: string | null
}

export type WorkspacePerson = {
  membership_id: number
  user_id: number
  public_id: string
  display_name: string
  display_email: string
  role: 'owner' | 'admin' | 'member'
  linked_consultant_id: number | null
  linked_consultant_name: string | null
}

export type WorkspaceInvitation = {
  invitation_id: number
  display_email: string
  role: 'admin' | 'member'
  linked_consultant_id: number | null
  status: 'pending'
  expires_at: string
}

export type WorkspaceManagement = {
  workspace_id: number
  revision: number
  workspace_name: string
  status: 'active' | 'closed'
  closed_at: string | null
  purge_after: string | null
  current_role: 'owner' | 'admin'
  people: WorkspacePerson[]
  invitations: WorkspaceInvitation[]
  consultants: { consultant_id: number; name: string }[]
  transfer: {
    transfer_id: number
    from_user_id: number
    to_user_id: number
    to_display_name: string
    expires_at: string
    can_accept: boolean
  } | null
  recent_events: {
    event_id: number
    actor_label: string
    event_type: string
    details: Record<string, unknown>
    recorded_at: string
  }[]
}

export type WorkspaceImpact = {
  consultants: number
  pending_invitations: number
  has_operational_history: boolean
  can_delete_immediately: boolean
}

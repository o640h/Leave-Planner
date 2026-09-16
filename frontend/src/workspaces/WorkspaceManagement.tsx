import { FormEvent, useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import {
  acceptOwnershipTransfer,
  closeWorkspace,
  deleteWorkspace,
  getWorkspaceImpact,
  getWorkspaceManagement,
  inviteWorkspacePerson,
  listManagedWorkspaces,
  recoverWorkspace,
  removeWorkspaceMember,
  renameWorkspace,
  requestOwnershipTransfer,
  resendWorkspaceInvitation,
  revokeWorkspaceInvitation,
  updateWorkspaceMember,
} from './api'
import type {
  ManagedWorkspace,
  WorkspaceImpact,
  WorkspaceManagement as WorkspaceManagementData,
  WorkspacePerson,
} from './types'

type WorkspaceManagementProps = {
  activeWorkspaceId: number | null
  onCreateWorkspace: () => void
  onWorkspaceContextChanged: (context: WorkspaceContext) => void
}

function displayEventName(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function PersonControls({
  person,
  management,
  busy,
  onChanged,
  onRemoved,
  onTransfer,
}: {
  person: WorkspacePerson
  management: WorkspaceManagementData
  busy: boolean
  onChanged: (
    person: WorkspacePerson,
    role: 'admin' | 'member',
    consultantId: number | null,
  ) => void
  onRemoved: (person: WorkspacePerson) => void
  onTransfer: (person: WorkspacePerson) => void
}) {
  const [role, setRole] = useState<'admin' | 'member'>(
    person.role === 'member' ? 'member' : 'admin',
  )
  const [consultantId, setConsultantId] = useState(person.linked_consultant_id?.toString() ?? '')
  const isOwner = person.role === 'owner'
  const currentUserCanChange =
    !isOwner && (management.current_role === 'owner' || person.role === 'member')

  return (
    <li className="workspace-person-row">
      <div>
        <strong>{person.display_name}</strong>
        <span>{person.display_email}</span>
      </div>
      <span className={`workspace-role workspace-role--${person.role}`}>{person.role}</span>
      {currentUserCanChange ? (
        <>
          {management.current_role === 'owner' ? (
            <select
              aria-label={`Role For ${person.display_name}`}
              value={role}
              disabled={busy}
              onChange={(event) => setRole(event.target.value as 'admin' | 'member')}
            >
              <option value="admin">Admin</option>
              <option value="member">Member</option>
            </select>
          ) : null}
          {role === 'member' ? (
            <select
              aria-label={`Consultant For ${person.display_name}`}
              value={consultantId}
              disabled={busy}
              onChange={(event) => setConsultantId(event.target.value)}
            >
              <option value="">Choose Consultant</option>
              {management.consultants.map((consultant) => (
                <option key={consultant.consultant_id} value={consultant.consultant_id}>
                  {consultant.name}
                </option>
              ))}
            </select>
          ) : null}
          <button
            className="button button--quiet"
            type="button"
            disabled={busy || (role === 'member' && !consultantId)}
            onClick={() => onChanged(person, role, consultantId ? Number(consultantId) : null)}
          >
            Save
          </button>
          <button
            className="button button--danger"
            type="button"
            disabled={busy}
            onClick={() => onRemoved(person)}
          >
            Remove
          </button>
          {management.current_role === 'owner' && person.role === 'admin' ? (
            <button
              className="button button--quiet"
              type="button"
              disabled={busy}
              onClick={() => onTransfer(person)}
            >
              Transfer Ownership
            </button>
          ) : null}
        </>
      ) : (
        <span className="workspace-person-link">
          {person.linked_consultant_name ?? 'Full Workspace Access'}
        </span>
      )}
    </li>
  )
}

export function WorkspaceManagement({
  activeWorkspaceId,
  onCreateWorkspace,
  onWorkspaceContextChanged,
}: WorkspaceManagementProps) {
  const [workspaces, setWorkspaces] = useState<ManagedWorkspace[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(activeWorkspaceId)
  const [management, setManagement] = useState<WorkspaceManagementData | null>(null)
  const [impact, setImpact] = useState<WorkspaceImpact | null>(null)
  const [name, setName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'admin' | 'member'>('member')
  const [inviteConsultantId, setInviteConsultantId] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [password, setPassword] = useState('')
  const [dangerOpen, setDangerOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const initialId = activeWorkspaceId
    const requests = initialId
      ? Promise.all([listManagedWorkspaces(), getWorkspaceManagement(initialId)])
      : listManagedWorkspaces().then(async (items) => {
          const first = items[0]
          return [items, first ? await getWorkspaceManagement(first.workspace_id) : null] as const
        })
    requests
      .then(([items, details]) => {
        if (!active) return
        setWorkspaces(items)
        setManagement(details)
        setSelectedId(details?.workspace_id ?? items[0]?.workspace_id ?? null)
        setName(details?.workspace_name ?? '')
      })
      .catch((requestError) => active && setError(operatorErrorMessage(requestError)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [activeWorkspaceId])

  async function refreshList(preferredId: number | null = selectedId) {
    const items = await listManagedWorkspaces()
    setWorkspaces(items)
    const nextId = preferredId ?? items[0]?.workspace_id ?? null
    setSelectedId(nextId)
    if (nextId) {
      const details = await getWorkspaceManagement(nextId)
      setManagement(details)
      setName(details.workspace_name)
    } else {
      setManagement(null)
      setName('')
    }
  }

  async function chooseWorkspace(workspaceId: number) {
    setSelectedId(workspaceId)
    setLoading(true)
    setError(null)
    setNotice(null)
    setDangerOpen(false)
    setImpact(null)
    try {
      const details = await getWorkspaceManagement(workspaceId)
      setManagement(details)
      setName(details.workspace_name)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  async function runMutation(action: () => Promise<WorkspaceManagementData>, message: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const details = await action()
      setManagement(details)
      setName(details.workspace_name)
      setNotice(message)
      const items = await listManagedWorkspaces()
      setWorkspaces(items)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function submitRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!management || !name.trim()) return
    await runMutation(
      () => renameWorkspace(management.workspace_id, name.trim()),
      'Workspace name updated.',
    )
  }

  async function submitInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!management || !inviteEmail.trim()) return
    await runMutation(
      () =>
        inviteWorkspacePerson(
          management.workspace_id,
          inviteEmail.trim(),
          inviteRole,
          inviteRole === 'member' && inviteConsultantId ? Number(inviteConsultantId) : null,
        ),
      'Invitation sent.',
    )
    setInviteEmail('')
  }

  async function openDangerZone() {
    if (!management) return
    setDangerOpen(true)
    setError(null)
    try {
      setImpact(await getWorkspaceImpact(management.workspace_id))
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    }
  }

  async function submitLifecycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!management || !impact) return
    setBusy(true)
    setError(null)
    try {
      const context = impact.can_delete_immediately
        ? await deleteWorkspace(management.workspace_id, confirmation)
        : await closeWorkspace(management.workspace_id, confirmation, password)
      onWorkspaceContextChanged(context)
      setNotice(impact.can_delete_immediately ? 'Workspace deleted.' : 'Workspace closed.')
      setDangerOpen(false)
      setConfirmation('')
      setPassword('')
      await refreshList(null)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  async function recoverSelected() {
    if (!management || !password) return
    setBusy(true)
    setError(null)
    try {
      await recoverWorkspace(management.workspace_id, password)
      setPassword('')
      setNotice('Workspace recovered.')
      await refreshList(management.workspace_id)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="settings-section workspace-management"
      aria-labelledby="workspace-settings-title"
    >
      <header className="settings-content-heading workspace-management-heading">
        <div>
          <span className="section-label">Account Access</span>
          <h2 id="workspace-settings-title">Workspaces</h2>
        </div>
        <button className="button button--primary" type="button" onClick={onCreateWorkspace}>
          Create Workspace
        </button>
      </header>

      {error ? (
        <p
          className="workspace-management-message workspace-management-message--error"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="workspace-management-message" role="status">
          {notice}
        </p>
      ) : null}

      <div className="workspace-management-layout">
        <aside className="workspace-list" aria-label="Your Workspaces">
          {workspaces.map((workspace) => (
            <button
              key={workspace.workspace_id}
              type="button"
              className={
                selectedId === workspace.workspace_id
                  ? 'workspace-list-item workspace-list-item--active'
                  : 'workspace-list-item'
              }
              onClick={() => chooseWorkspace(workspace.workspace_id)}
            >
              <strong>{workspace.workspace_name}</strong>
              <span>
                {workspace.role} · {workspace.status}
                {workspace.workspace_id === activeWorkspaceId ? ' · Active Selection' : ''}
              </span>
            </button>
          ))}
          {!loading && workspaces.length === 0 ? <p>No managed workspaces.</p> : null}
        </aside>

        <div className="workspace-management-detail">
          {loading ? <p role="status">Loading Workspace…</p> : null}
          {!loading && management ? (
            <>
              <section className="settings-panel workspace-detail-panel">
                <header>
                  <div>
                    <h3>{management.workspace_name}</h3>
                    <p>Your role is {management.current_role}.</p>
                  </div>
                  <span className={`workspace-state workspace-state--${management.status}`}>
                    {management.status}
                  </span>
                </header>
                {management.status === 'active' && management.current_role === 'owner' ? (
                  <form className="workspace-inline-form" noValidate onSubmit={submitRename}>
                    <label htmlFor="workspace-name">Workspace Name</label>
                    <input
                      id="workspace-name"
                      value={name}
                      maxLength={160}
                      onChange={(event) => setName(event.target.value)}
                    />
                    <button
                      className="button button--quiet"
                      type="submit"
                      disabled={busy || !name.trim()}
                    >
                      Save Name
                    </button>
                  </form>
                ) : null}
              </section>

              {management.status === 'active' ? (
                <>
                  <section className="settings-panel workspace-detail-panel">
                    <header>
                      <div>
                        <h3>People</h3>
                        <p>Workspace roles and consultant links.</p>
                      </div>
                    </header>
                    {management.transfer ? (
                      <div className="workspace-transfer-notice">
                        <span>
                          Ownership transfer to {management.transfer.to_display_name} is pending.
                        </span>
                        {management.transfer.can_accept ? (
                          <button
                            className="button button--primary"
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              runMutation(
                                () =>
                                  acceptOwnershipTransfer(
                                    management.workspace_id,
                                    management.transfer!.transfer_id,
                                  ),
                                'Ownership accepted.',
                              )
                            }
                          >
                            Accept Ownership
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                    <ul className="workspace-people-list">
                      {management.people.map((person) => (
                        <PersonControls
                          key={person.membership_id}
                          person={person}
                          management={management}
                          busy={busy}
                          onChanged={(target, role, consultantId) =>
                            runMutation(
                              () =>
                                updateWorkspaceMember(
                                  management.workspace_id,
                                  target.membership_id,
                                  role,
                                  consultantId,
                                ),
                              `${target.display_name} updated.`,
                            )
                          }
                          onRemoved={(target) =>
                            runMutation(
                              () =>
                                removeWorkspaceMember(
                                  management.workspace_id,
                                  target.membership_id,
                                ),
                              `${target.display_name} removed.`,
                            )
                          }
                          onTransfer={(target) =>
                            runMutation(
                              () =>
                                requestOwnershipTransfer(
                                  management.workspace_id,
                                  target.membership_id,
                                ),
                              `Ownership transfer sent to ${target.display_name}.`,
                            )
                          }
                        />
                      ))}
                    </ul>
                  </section>

                  <section className="settings-panel workspace-detail-panel">
                    <header>
                      <div>
                        <h3>Invite Person</h3>
                        <p>Invitations expire after seven days and can be used once.</p>
                      </div>
                    </header>
                    <form className="workspace-invite-form" noValidate onSubmit={submitInvitation}>
                      <label htmlFor="workspace-invite-email">Email</label>
                      <input
                        id="workspace-invite-email"
                        type="email"
                        value={inviteEmail}
                        onChange={(event) => setInviteEmail(event.target.value)}
                      />
                      <label htmlFor="workspace-invite-role">Role</label>
                      <select
                        id="workspace-invite-role"
                        value={inviteRole}
                        onChange={(event) =>
                          setInviteRole(event.target.value as 'admin' | 'member')
                        }
                      >
                        {management.current_role === 'owner' ? (
                          <option value="admin">Admin</option>
                        ) : null}
                        <option value="member">Member</option>
                      </select>
                      {inviteRole === 'member' ? (
                        <>
                          <label htmlFor="workspace-invite-consultant">Consultant</label>
                          <select
                            id="workspace-invite-consultant"
                            value={inviteConsultantId}
                            onChange={(event) => setInviteConsultantId(event.target.value)}
                          >
                            <option value="">Choose Consultant</option>
                            {management.consultants.map((consultant) => (
                              <option
                                key={consultant.consultant_id}
                                value={consultant.consultant_id}
                              >
                                {consultant.name}
                              </option>
                            ))}
                          </select>
                        </>
                      ) : null}
                      <button
                        className="button button--primary"
                        type="submit"
                        disabled={
                          busy ||
                          !inviteEmail.trim() ||
                          (inviteRole === 'member' && !inviteConsultantId)
                        }
                      >
                        Send Invitation
                      </button>
                    </form>
                    {management.invitations.length ? (
                      <ul className="workspace-invitation-list">
                        {management.invitations.map((invitation) => (
                          <li key={invitation.invitation_id}>
                            <div>
                              <strong>{invitation.display_email}</strong>
                              <span>
                                {invitation.role} · Expires{' '}
                                {new Date(invitation.expires_at).toLocaleDateString()}
                              </span>
                            </div>
                            <button
                              className="button button--quiet"
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                runMutation(
                                  () =>
                                    resendWorkspaceInvitation(
                                      management.workspace_id,
                                      invitation.invitation_id,
                                    ),
                                  'Invitation resent.',
                                )
                              }
                            >
                              Resend
                            </button>
                            <button
                              className="button button--danger"
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                runMutation(
                                  () =>
                                    revokeWorkspaceInvitation(
                                      management.workspace_id,
                                      invitation.invitation_id,
                                    ),
                                  'Invitation revoked.',
                                )
                              }
                            >
                              Revoke
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </section>
                </>
              ) : (
                <section className="settings-panel workspace-detail-panel">
                  <header>
                    <div>
                      <h3>Closed Workspace</h3>
                      <p>
                        Recover this workspace before{' '}
                        {management.purge_after
                          ? new Date(management.purge_after).toLocaleDateString()
                          : 'the recovery deadline'}
                        .
                      </p>
                    </div>
                  </header>
                  <div className="workspace-inline-form">
                    <label htmlFor="workspace-recovery-password">Password</label>
                    <input
                      id="workspace-recovery-password"
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                    <button
                      className="button button--primary"
                      type="button"
                      disabled={busy || !password}
                      onClick={recoverSelected}
                    >
                      Recover Workspace
                    </button>
                  </div>
                </section>
              )}

              <section className="settings-panel workspace-detail-panel">
                <header>
                  <div>
                    <h3>Recent Changes</h3>
                    <p>Workspace membership and lifecycle activity.</p>
                  </div>
                </header>
                <ol className="workspace-event-list">
                  {management.recent_events.map((event) => (
                    <li key={event.event_id}>
                      <strong>{displayEventName(event.event_type)}</strong>
                      <span>
                        {event.actor_label} · {new Date(event.recorded_at).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ol>
              </section>

              {management.status === 'active' && management.current_role === 'owner' ? (
                <section className="settings-panel workspace-detail-panel workspace-danger-zone">
                  <header>
                    <div>
                      <h3>Workspace Lifecycle</h3>
                      <p>
                        Empty setup mistakes can be deleted. Workspaces with operational history
                        enter a 30-day recovery period.
                      </p>
                    </div>
                    <button
                      className="button button--danger"
                      type="button"
                      onClick={openDangerZone}
                    >
                      Review Removal
                    </button>
                  </header>
                  {dangerOpen && impact ? (
                    <form className="workspace-danger-form" noValidate onSubmit={submitLifecycle}>
                      <p>
                        {impact.can_delete_immediately
                          ? 'This empty workspace will be deleted immediately.'
                          : `This workspace contains ${impact.consultants} consultant record${impact.consultants === 1 ? '' : 's'} and will be closed for 30 days.`}
                      </p>
                      <label htmlFor="workspace-confirmation">
                        Type {management.workspace_name} To Confirm
                      </label>
                      <input
                        id="workspace-confirmation"
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                      />
                      {!impact.can_delete_immediately ? (
                        <>
                          <label htmlFor="workspace-close-password">Password</label>
                          <input
                            id="workspace-close-password"
                            type="password"
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                          />
                        </>
                      ) : null}
                      <button
                        className="button button--danger"
                        type="submit"
                        disabled={
                          busy ||
                          confirmation !== management.workspace_name ||
                          (!impact.can_delete_immediately && !password)
                        }
                      >
                        {impact.can_delete_immediately ? 'Delete Workspace' : 'Close Workspace'}
                      </button>
                    </form>
                  ) : null}
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  )
}

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { WorkspaceManagement } from './WorkspaceManagement'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const managed = [
  {
    workspace_id: 1,
    workspace_name: 'Consultants',
    role: 'owner',
    status: 'active',
    closed_at: null,
    purge_after: null,
  },
]

const detail = {
  workspace_id: 1,
  workspace_name: 'Consultants',
  status: 'active',
  closed_at: null,
  purge_after: null,
  current_role: 'owner',
  people: [
    {
      membership_id: 1,
      user_id: 1,
      public_id: 'owner-public-id',
      display_name: 'Primary Owner',
      display_email: 'owner@example.org',
      role: 'owner',
      linked_consultant_id: null,
      linked_consultant_name: null,
    },
  ],
  invitations: [],
  consultants: [{ consultant_id: 7, name: 'Dr Member' }],
  transfer: null,
  recent_events: [],
}

describe('workspace management', () => {
  it('lists managed workspaces and keeps creation in the page header', async () => {
    const onCreateWorkspace = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/workspaces/managed') return Promise.resolve(json(managed))
        if (path === '/api/workspaces/1/management') return Promise.resolve(json(detail))
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    const user = userEvent.setup()
    render(
      <WorkspaceManagement
        activeWorkspaceId={1}
        onCreateWorkspace={onCreateWorkspace}
        onWorkspaceContextChanged={vi.fn()}
      />,
    )

    expect(await screen.findByRole('heading', { name: 'Workspaces' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'People' })).toBeInTheDocument()
    expect(screen.getByText('Primary Owner')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create Workspace' }))
    expect(onCreateWorkspace).toHaveBeenCalledOnce()
  })

  it('shows the immediate-delete impact for an empty setup workspace', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/workspaces/managed') return Promise.resolve(json(managed))
        if (path === '/api/workspaces/1/management') return Promise.resolve(json(detail))
        if (path === '/api/workspaces/1/impact') {
          return Promise.resolve(
            json({
              consultants: 0,
              pending_invitations: 0,
              has_operational_history: false,
              can_delete_immediately: true,
            }),
          )
        }
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    const user = userEvent.setup()
    render(
      <WorkspaceManagement
        activeWorkspaceId={1}
        onCreateWorkspace={vi.fn()}
        onWorkspaceContextChanged={vi.fn()}
      />,
    )
    await user.click(await screen.findByRole('button', { name: 'Review Removal' }))

    await waitFor(() =>
      expect(
        screen.getByText('This empty workspace will be deleted immediately.'),
      ).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Delete Workspace' })).toBeDisabled()
  })
})

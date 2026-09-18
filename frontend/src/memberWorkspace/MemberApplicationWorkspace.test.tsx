import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MemberApplicationWorkspace } from './MemberApplicationWorkspace'
import type { MemberWorkspaceData } from './types'

function json(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) }
}

const workspace = {
  state: 'active' as const,
  active_workspace_id: 1,
  memberships: [
    {
      workspace_id: 1,
      workspace_name: 'Clinical Services',
      role: 'member' as const,
      linked_consultant_id: 12,
    },
  ],
}

const memberData: MemberWorkspaceData = {
  state: 'linked',
  workspace_name: 'Clinical Services',
  consultant: { name: 'Alex Morgan', post_title: 'Consultant in Radiology' },
  leave_years: [
    {
      id: 9,
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      employment_start: null,
      employment_end: null,
    },
  ],
  selected_year: {
    leave_year: {
      id: 9,
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      employment_start: null,
      employment_end: null,
    },
    job_plans: [],
    entitlement: { recommendation: null, application: null },
    carry_forward: { dcc_hours: '0', spa_hours: '0', total_hours: '0' },
    allocation_source: null,
    job_plan_periods: [],
    holidays: [],
    bookings: [],
    balances: { requested: null, approved: null },
    weekday_counts: { monday: 0, tuesday: 0, wednesday: 0, thursday: 0, friday: 0 },
    warnings: [{ code: 'job-plan.required', message: 'A job plan is required.', severity: 'info' }],
  },
}

describe('Member application workspace', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the linked consultant as read only without operator actions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/member/workspace') return Promise.resolve(json(memberData))
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={vi.fn()}
      />,
    )

    expect(await screen.findByRole('heading', { name: 'Alex Morgan' })).toBeInTheDocument()
    expect(screen.getByText('Consultant in Radiology')).toBeInTheDocument()
    expect(screen.queryByText('Leave Setup Status')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument()
    expect(screen.queryByText('Recent Changes')).not.toBeInTheDocument()
  })

  it('keeps a Settings destination while showing Members only relevant categories', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/member/workspace') return Promise.resolve(json(memberData))
        if (path === '/api/policies') return Promise.resolve(json([]))
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={vi.fn()}
      />,
    )
    await screen.findByRole('heading', { name: 'Alex Morgan' })
    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Policy & Guidance' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Workspace' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Public Holidays' })).not.toBeInTheDocument()
  })

  it('offers workspace switching and creation from a single Member workspace', async () => {
    const user = userEvent.setup()
    const onCreateWorkspace = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/member/workspace') return Promise.resolve(json(memberData))
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={onCreateWorkspace}
      />,
    )
    await screen.findByRole('heading', { name: 'Alex Morgan' })
    await user.click(screen.getByRole('button', { name: 'Switch Workspace' }))

    const dialog = screen.getByRole('dialog', { name: 'Choose Workspace' })
    expect(within(dialog).getByText('Clinical Services')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Create Workspace' }))

    await waitFor(() => expect(onCreateWorkspace).toHaveBeenCalledOnce())
  })

  it('previews and submits a Member leave request without operator-controlled fields', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
      if (path === '/api/member/workspace') return Promise.resolve(json(memberData))
      if (path.endsWith('/requests/preview')) {
        return Promise.resolve(
          json({
            days: [
              {
                leave_date: '2026-09-28',
                deduction: {
                  dcc_hours: '8',
                  spa_hours: '0',
                  other_hours: '0',
                  total_hours: '8',
                },
              },
            ],
            requested: null,
            approved: null,
            warnings: [],
          }),
        )
      }
      if (path.endsWith('/requests') && init?.method === 'POST') {
        return Promise.resolve(json(memberData))
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={vi.fn()}
      />,
    )
    await screen.findByRole('heading', { name: 'Alex Morgan' })
    await user.click(screen.getByRole('button', { name: 'Request Leave' }))
    fireEvent.change(document.getElementById('member-request-start') as HTMLInputElement, {
      target: { value: '2026-09-28' },
    })
    fireEvent.change(document.getElementById('member-request-end') as HTMLInputElement, {
      target: { value: '2026-09-28' },
    })

    const submit = await screen.findByRole('button', { name: 'Submit Request' })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/member/leave-years/9/requests',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    const requestCall = fetchMock.mock.calls.find(([path]) => path.toString().endsWith('/requests'))
    expect(JSON.parse(String(requestCall?.[1]?.body))).toEqual({
      start_date: '2026-09-28',
      end_date: '2026-09-28',
      note: null,
    })
  })

  it('renders booking states without private colleague details on the shared wallchart', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/member/workspace') return Promise.resolve(json(memberData))
        if (path.startsWith('/api/member/wallchart')) {
          return Promise.resolve(
            json({
              month: '2026-09-01',
              holidays: [],
              people: [
                {
                  display_name: 'Team Colleague',
                  leave_dates: [{ leave_date: '2026-09-21', state: 'requested' }],
                },
              ],
            }),
          )
        }
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={vi.fn()}
      />,
    )
    await screen.findByRole('heading', { name: 'Alex Morgan' })
    await user.click(screen.getByRole('button', { name: 'Team Wallchart' }))

    const wallchart = await screen.findByRole('grid', { name: /Team availability/i })
    expect(within(wallchart).getByText('Team Colleague')).toBeInTheDocument()
    expect(
      screen.queryByText('Team leave is shown by its current booking status.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Requested')).toBeInTheDocument()
    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.queryByText('Taken')).not.toBeInTheDocument()
    expect(screen.queryByText(/DCC|SPA|Private note/)).not.toBeInTheDocument()
  })

  it('shows an unlinked Member only the waiting-for-access state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/member/workspace') {
          return Promise.resolve(
            json({
              state: 'waiting',
              workspace_name: 'Clinical Services',
              consultant: null,
              leave_years: [],
              selected_year: null,
            }),
          )
        }
        throw new Error(`Unexpected request: ${path}`)
      }),
    )

    render(
      <MemberApplicationWorkspace
        user={{ public_id: 'member', display_name: 'Alex', display_email: 'alex@example.org' }}
        workspace={workspace}
        onSignOut={vi.fn()}
        onWorkspaceSelected={vi.fn()}
        onCreateWorkspace={vi.fn()}
      />,
    )

    expect(
      await screen.findByRole('heading', { name: 'Waiting For Consultant Access' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Primary navigation' })).not.toBeInTheDocument()
    expect(screen.queryByText('Alex Morgan')).not.toBeInTheDocument()
  })
})

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApplicationWorkspace } from './App'
import type { Consultant } from './consultants/types'

function json(body: unknown, ok = true) {
  return { ok, json: () => Promise.resolve(body) }
}

describe('consultant directory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.localStorage.clear()
    delete document.documentElement.dataset.theme
    delete document.documentElement.dataset.themePreference
  })

  it('creates and edits a consultant through the visible workflow', async () => {
    const user = userEvent.setup()
    const consultants: Consultant[] = []

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        const method = options.method ?? 'GET'

        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants' && method === 'GET') return json(consultants)
        if (path === '/api/consultants/1/leave-years' && method === 'GET') return json([])
        if (path === '/api/consultants/1/archive-impact') {
          return json({
            resource_name: 'Dr Alex Morgan',
            action: 'archive',
            confirmation_text: 'Dr Alex Morgan',
            consequences: ['The consultant will disappear from the active directory.'],
            can_proceed: true,
            blocking_reason: null,
          })
        }
        if (path === '/api/consultants/1/archive' && method === 'POST') {
          consultants.splice(0)
          return json({
            message: 'Dr Alex Morgan was archived.',
            entitlement_status: 'not_applicable',
          })
        }

        const details = JSON.parse(options.body as string) as Omit<Consultant, 'id'>
        if (path === '/api/consultants' && method === 'POST') {
          const created = { id: 1, ...details }
          consultants.push(created)
          return json(created)
        }
        if (path === '/api/consultants/1' && method === 'PUT') {
          consultants[0] = { id: 1, ...details }
          return json(consultants[0])
        }
        throw new Error(`Unexpected request: ${method} ${path}`)
      }),
    )

    render(<ApplicationWorkspace />)

    expect(await screen.findByText('Ready')).toBeInTheDocument()
    expect(await screen.findByText('No consultants have been added.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add Consultant' }))
    expect(screen.getByRole('dialog', { name: 'Add Consultant' })).toBeInTheDocument()

    await user.type(screen.getByRole('textbox', { name: 'Consultant Name' }), 'Dr Alex Morgan')
    await user.type(
      screen.getByRole('textbox', { name: 'Post Title (Optional)' }),
      'Consultant in Radiology',
    )
    await user.click(screen.getByRole('button', { name: 'Create Consultant' }))

    expect(await screen.findAllByText('Consultant in Radiology')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: 'Edit Consultant' }))
    const editDialog = screen.getByRole('dialog', { name: 'Edit Consultant' })
    const postTitle = within(editDialog).getByRole('textbox', {
      name: 'Post Title (Optional)',
    })
    await user.clear(postTitle)
    await user.type(postTitle, 'Clinical Lead')
    await user.click(within(editDialog).getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findAllByText('Clinical Lead')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: 'Archive' }))
    const archiveDialog = await screen.findByRole('dialog', { name: 'Archive Consultant' })
    await user.type(within(archiveDialog).getByRole('textbox'), 'Dr Alex Morgan')
    await user.click(within(archiveDialog).getByRole('button', { name: 'Archive' }))
    expect(await screen.findByText('No Consultant Selected')).toBeInTheDocument()
  }, 10_000)

  it('uses Title Case for short interface labels', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(json(input.toString() === '/api/health' ? { status: 'ok' } : [])),
      ),
    )

    render(<ApplicationWorkspace />)
    expect(await screen.findByRole('heading', { name: 'Consultants' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Consultant' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Consultants' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('organises settings into focused categories', async () => {
    const user = userEvent.setup()

    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/consultants') return Promise.resolve(json([]))
        if (path === '/api/settings/public-holidays') {
          return Promise.resolve(
            json({
              source: 'static_snapshot',
              source_date: '2026-08-10',
              holidays: [],
              corrections: [],
            }),
          )
        }
        throw new Error(`Unexpected request: GET ${path}`)
      }),
    )

    render(<ApplicationWorkspace />)
    await user.click(screen.getByRole('button', { name: 'Settings' }))

    expect(screen.getByRole('heading', { name: 'Workspaces' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Appearance' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Data & Recovery' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Public Holidays' }))
    expect(await screen.findByRole('heading', { name: 'Public Holidays' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'England & Wales Calendar' })).toBeInTheDocument()
  })

  it('filters the consultant directory without changing the selected workspace', async () => {
    const user = userEvent.setup()
    const consultant = {
      id: 1,
      name: 'Dr Alex Morgan',
      post_title: 'Consultant in Radiology',
      archived_at: null,
    }

    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
        if (path === '/api/consultants') return Promise.resolve(json([consultant]))
        return Promise.resolve(json([]))
      }),
    )

    render(<ApplicationWorkspace />)
    expect(await screen.findByRole('heading', { name: 'Dr Alex Morgan' })).toBeInTheDocument()

    const search = screen.getByRole('searchbox', { name: 'Search' })
    await user.type(search, 'missing')
    expect(screen.getByText('No matching consultants.')).toBeInTheDocument()

    // Filtering the list must not discard the consultant already open in the workspace.
    expect(screen.getByRole('heading', { name: 'Dr Alex Morgan' })).toBeInTheDocument()
    await user.clear(search)
    expect(screen.queryByText('No matching consultants.')).not.toBeInTheDocument()
  })

  it('creates and edits a leave year for the selected consultant', async () => {
    const user = userEvent.setup()
    const consultant: Consultant = {
      id: 1,
      name: 'Dr Alex Morgan',
      post_title: 'Consultant in Radiology',
      archived_at: null,
    }
    const leaveYears: Array<Record<string, unknown>> = []

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        const method = options.method ?? 'GET'

        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants') return json([consultant])
        if (path === '/api/consultants/1/leave-years' && method === 'GET') {
          return json(leaveYears)
        }
        if (path.endsWith('/job-plans') && method === 'GET') return json([])

        const details = JSON.parse(options.body as string) as Record<string, unknown>
        if (path === '/api/consultants/1/leave-years' && method === 'POST') {
          const created = { id: 1, consultant_id: 1, ...details }
          leaveYears.push(created)
          return json(created)
        }
        if (path === '/api/consultants/1/leave-years/1' && method === 'PUT') {
          leaveYears[0] = { id: 1, consultant_id: 1, ...details }
          return json(leaveYears[0])
        }
        throw new Error(`Unexpected request: ${method} ${path}`)
      }),
    )

    render(<ApplicationWorkspace />)
    expect(await screen.findByText('No Leave Year Configured')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add Leave Year' }))
    await user.type(screen.getByLabelText('Annual Leave Year Start'), '2025-08-29')
    await user.type(screen.getByLabelText('Annual Leave Year End'), '2026-08-28')
    await user.click(screen.getByRole('button', { name: 'Create Leave Year' }))

    expect(await screen.findByText('29 Aug 2025')).toBeInTheDocument()
    expect(screen.getByText('28 Aug 2026')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const editor = screen.getByRole('dialog', { name: 'Edit Leave Year' })
    await user.type(within(editor).getByLabelText('Employment Start (Optional)'), '2026-01-01')
    await user.click(within(editor).getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText('1 Jan 2026')).toBeInTheDocument()
  })

  it('uses quiet inline validation instead of the browser validation popup', async () => {
    const user = userEvent.setup()

    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(json(input.toString() === '/api/health' ? { status: 'ok' } : [])),
      ),
    )

    render(<ApplicationWorkspace />)
    await screen.findByText('No consultants have been added.')
    await user.click(screen.getByRole('button', { name: 'Add Consultant' }))

    const form = screen.getByRole('dialog', { name: 'Add Consultant' }).querySelector('form')
    expect(form).toHaveAttribute('novalidate')

    await user.click(screen.getByRole('button', { name: 'Create Consultant' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a consultant name.')
  })

  it('calculates Total PA from DCC and SPA, then previews and saves the job plan', async () => {
    const user = userEvent.setup()
    const consultant = {
      id: 1,
      name: 'Dr Alex Morgan',
      post_title: 'Consultant in Radiology',
      archived_at: null,
    }
    const leaveYear = {
      id: 1,
      consultant_id: 1,
      start_date: '2025-08-29',
      end_date: '2026-08-28',
      employment_start: null,
      employment_end: null,
    }
    const jobPlans: Array<Record<string, unknown>> = []
    let entitlementRefreshes = 0

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        const method = options.method ?? 'GET'

        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants') return json([consultant])
        if (path === '/api/consultants/1/leave-years') return json([leaveYear])
        if (path.endsWith('/job-plans') && method === 'GET') return json(jobPlans)
        if (path.endsWith('/entitlement') && method === 'GET') {
          return json({ recommendation: null, application: null })
        }
        if (path.endsWith('/entitlement/refresh') && method === 'POST') {
          entitlementRefreshes += 1
          return json({ recommendation: null, application: null })
        }
        if (path.endsWith('/carry-forward') && method === 'GET') {
          return json({
            id: null,
            leave_year_id: 1,
            dcc_hours: '0',
            spa_hours: '0',
            total_hours: '0',
            created_at: null,
          })
        }
        if (path.endsWith('/public-holidays') && method === 'GET') {
          return json({
            source: 'static_snapshot',
            source_date: '2026-08-06',
            entitlement_hours: '0',
            deduction_hours: '0',
            occurrences: [],
          })
        }

        const details = JSON.parse(options.body as string) as Record<string, unknown>
        if (path.endsWith('/job-plans/preview')) {
          const allocated =
            Number(details.dcc_pas) + Number(details.spa_pas) + Number(details.other_pas)
          const variance = allocated - Number(details.contracted_pas)
          return json({
            ...details,
            allocated_pas: allocated.toFixed(3),
            reconciliation_variance: variance.toFixed(3),
            is_reconciled: variance === 0,
            average_visible_hours: '0',
            average_dcc_hours: '0',
            average_spa_hours: '0',
            average_other_hours: '0',
            scheduled_average_pas: '0',
            warning: variance === 0 ? null : 'Enter an override reason before saving.',
          })
        }
        if (path.endsWith('/job-plans') && method === 'POST') {
          const created = { id: 1, leave_year_id: 1, ...details }
          jobPlans.push(created)
          return json(created)
        }
        if (path.endsWith('/job-plans/1/update-impact') && method === 'POST') {
          return json({
            affected_bookings: 0,
            affected_booking_days: 0,
            current_dcc_hours: '0',
            current_spa_hours: '0',
            current_total_hours: '0',
            updated_dcc_hours: '0',
            updated_spa_hours: '0',
            updated_total_hours: '0',
            difference_hours: '0',
            requires_confirmation: false,
          })
        }
        if (path.endsWith('/job-plans/1') && method === 'PUT') {
          jobPlans[0] = { id: 1, leave_year_id: 1, ...details }
          return json(jobPlans[0])
        }
        throw new Error(`Unexpected request: ${method} ${path}`)
      }),
    )

    render(<ApplicationWorkspace />)
    expect(
      await screen.findByText('No job plan is configured for this leave year.'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add Job Plan' }))
    const dialog = screen.getByRole('dialog', { name: 'Add Job Plan' })
    // Total PA is deliberately not an input: changing either activity updates it exactly.
    for (const [label, value] of [
      ['DCC PAs', '5.91'],
      ['SPA PAs', '2.56'],
    ]) {
      const input = within(dialog).getByLabelText(label)
      await user.clear(input)
      await user.type(input, value)
    }
    expect(within(dialog).getByLabelText('Total PA')).toHaveTextContent('8.47')

    await user.click(within(dialog).getByRole('button', { name: 'Preview Job Plan' }))
    expect(await within(dialog).findByText('PA Split Reconciled')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Create Job Plan' }))
    expect(await screen.findByText('Job Plan 1')).toBeInTheDocument()
    await waitFor(() => expect(entitlementRefreshes).toBe(1))

    await user.click(
      within(screen.getByRole('region', { name: 'Job Plans' })).getByRole('button', {
        name: 'Edit',
      }),
    )
    const editDialog = screen.getByRole('dialog', { name: 'Edit Job Plan' })
    const spaPas = within(editDialog).getByLabelText('SPA PAs')
    await user.clear(spaPas)
    await user.type(spaPas, '2.5')
    expect(within(editDialog).getByLabelText('Total PA')).toHaveTextContent('8.41')
    await user.click(within(editDialog).getByRole('button', { name: 'Preview Job Plan' }))

    expect(await within(editDialog).findByText('PA Split Reconciled')).toBeInTheDocument()
    await user.click(within(editDialog).getByRole('button', { name: 'Save Changes' }))
    expect(await screen.findByText('8.41')).toBeInTheDocument()
    await waitFor(() => expect(entitlementRefreshes).toBe(2))
  })
})

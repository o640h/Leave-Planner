import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { JobPlanPanel } from './JobPlanPanel'
import type { JobPlan, JobPlanInput } from './types'

vi.mock('./JobPlanForm', () => ({
  JobPlanForm: ({
    initialValue,
    onSubmit,
  }: {
    initialValue: JobPlanInput
    onSubmit: (details: JobPlanInput) => Promise<void>
  }) => (
    <button
      type="button"
      onClick={() =>
        onSubmit({
          ...initialValue,
          contracted_pas: '10.5',
          dcc_pas: '8',
          spa_pas: '2.5',
        })
      }
    >
      Save Changes
    </button>
  ),
}))

const plan: JobPlan = {
  id: 4,
  leave_year_id: 2,
  effective_from: '2025-08-29',
  effective_until: '2026-08-29',
  cycle_anchor_date: '2025-08-25',
  week_count: 1,
  contracted_pas: '8.47',
  dcc_pas: '5.91',
  spa_pas: '2.56',
  other_pas: '0',
  hours_per_pa: '4',
  reconciliation_override_reason: null,
  days: Array.from({ length: 7 }, (_, weekday) => ({
    cycle_week: 1,
    weekday,
    dcc_hours: weekday === 0 ? '8' : '0',
    spa_hours: weekday === 0 ? '0.5' : '0',
    other_hours: '0',
  })),
}

function json(body: unknown) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) }
}

describe('job plan deduction impact', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('requires confirmation before updating affected booking snapshots', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = input.toString()
      const method = options.method ?? 'GET'
      if (path.endsWith('/job-plans') && method === 'GET') return json([plan])
      if (path.endsWith('/job-plans/preview') && method === 'POST') {
        const details = JSON.parse(options.body as string) as JobPlanInput
        return json({
          ...details,
          allocated_pas: '10.5',
          reconciliation_variance: '0',
          is_reconciled: true,
          average_visible_hours: '8.5',
          average_dcc_hours: '8',
          average_spa_hours: '0.5',
          average_other_hours: '0',
          scheduled_average_pas: '2.125',
          warning: null,
        })
      }
      if (path.endsWith('/job-plans/4/update-impact') && method === 'POST') {
        return json({
          affected_bookings: 1,
          affected_booking_days: 1,
          current_dcc_hours: '8',
          current_spa_hours: '0.5',
          current_total_hours: '8.5',
          updated_dcc_hours: '7.619047619',
          updated_spa_hours: '0.476190476',
          updated_total_hours: '8.095238095',
          difference_hours: '-0.404761905',
          requires_confirmation: true,
        })
      }
      if (path.endsWith('/job-plans/4?regenerate_booking_days=true') && method === 'PUT') {
        return json({
          ...plan,
          ...JSON.parse(options.body as string),
          contracted_pas: '10.5',
          dcc_pas: '8',
          spa_pas: '2.5',
        })
      }
      throw new Error(`Unexpected request: ${method} ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const onSaved = vi.fn()
    render(
      <JobPlanPanel
        consultantId={1}
        leaveYear={{
          id: 2,
          consultant_id: 1,
          start_date: '2025-08-29',
          end_date: '2026-08-28',
          employment_start: null,
          employment_end: null,
        }}
        onSaved={onSaved}
      />,
    )

    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    const dialog = await screen.findByRole('dialog', { name: 'Recalculate Leave Deductions' })
    expect(within(dialog).getByText('8.5h')).toBeInTheDocument()
    expect(within(dialog).getByText('8.1h')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining('regenerate_booking_days=true'),
      expect.anything(),
    )

    await user.click(within(dialog).getByRole('button', { name: 'Update and Recalculate' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce())
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('regenerate_booking_days=true'),
      expect.objectContaining({ method: 'PUT' }),
    )
    expect(
      await screen.findByText('The job plan and affected leave deductions were updated.'),
    ).toBeInTheDocument()
  })
})

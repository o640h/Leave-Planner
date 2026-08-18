import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { JobPlanForm } from './JobPlanForm'
import type { JobPlanInput, JobPlanPreview } from './types'

it('accepts a one-day inclusive effective period', async () => {
  const user = userEvent.setup()
  // Equal visible dates describe one complete calendar day, not an empty period.
  const input: JobPlanInput = {
    effective_from: '2026-08-28',
    effective_until: '2026-08-28',
    cycle_anchor_date: null,
    week_count: 1,
    contracted_pas: '0',
    dcc_pas: '0',
    spa_pas: '0',
    other_pas: '0',
    hours_per_pa: '4',
    reconciliation_override_reason: null,
    days: Array.from({ length: 7 }, (_, weekday) => ({
      cycle_week: 1,
      weekday,
      dcc_hours: '0',
      spa_hours: '0',
      other_hours: '0',
    })),
  }
  const preview: JobPlanPreview = {
    ...input,
    allocated_pas: '0',
    reconciliation_variance: '0',
    is_reconciled: true,
    average_visible_hours: '0',
    average_dcc_hours: '0',
    average_spa_hours: '0',
    average_other_hours: '0',
    scheduled_average_pas: '0',
    warning: null,
  }
  const onPreview = vi.fn().mockResolvedValue(preview)
  const onSubmit = vi.fn().mockResolvedValue(undefined)

  render(
    <JobPlanForm
      initialValue={input}
      mode="create"
      busy={false}
      onPreview={onPreview}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
    />,
  )

  await user.click(screen.getByRole('button', { name: 'Create Job Plan' }))

  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(input))
  expect(screen.queryByText('Effective Until must be on or after Effective From.')).toBeNull()
})

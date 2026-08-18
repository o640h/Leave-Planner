import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { EntitlementForm } from './EntitlementForm'
import type { EntitlementRecommendation, EntitlementWorkspace } from './types'

const emptyWorkspace: EntitlementWorkspace = {
  recommendation: null,
  application: null,
}

const recommendation: EntitlementRecommendation = {
  inputs: {
    seven_years_or_more: true,
    policy_versions: ['HR78-v3'],
    public_holiday_source: 'static_snapshot',
    public_holiday_source_date: '2026-08-06',
  },
  base_entitlement: {
    dcc_hours: '170.073',
    spa_hours: '73.863',
    other_hours: '0',
    total_hours: '243.936',
  },
  public_holiday_entitlement: {
    dcc_hours: '33.231',
    spa_hours: '14.201',
    other_hours: '0',
    total_hours: '47.432',
  },
  recommended_entitlement: {
    dcc_hours: '203.304',
    spa_hours: '88.064',
    other_hours: '0',
    total_hours: '291.368',
  },
  components: [],
  trace: [],
}

it('previews the calculation before applying the recommended values', async () => {
  const user = userEvent.setup()
  const onPreview = vi.fn().mockResolvedValue(recommendation)
  const onSubmit = vi.fn().mockResolvedValue(undefined)

  render(
    <EntitlementForm
      initialValue={emptyWorkspace}
      busy={false}
      onPreview={onPreview}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
    />,
  )

  await user.click(screen.getByRole('checkbox', { name: /Seven Years or More/ }))
  await user.click(screen.getByRole('button', { name: 'Preview Recommendation' }))

  expect(onPreview).toHaveBeenCalledWith(true)
  expect(await screen.findByText('291.368')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Apply Entitlement' }))
  expect(onSubmit).toHaveBeenCalledWith({
    mode: 'calculated',
    other_hours: '0',
    seven_years_or_more: true,
  })
})

it('accepts manual values without an explanation', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn().mockResolvedValue(undefined)

  render(
    <EntitlementForm
      initialValue={emptyWorkspace}
      busy={false}
      onPreview={vi.fn()}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
    />,
  )

  await user.click(screen.getByRole('radio', { name: /Enter Manually/ }))
  await user.type(screen.getByLabelText('DCC Hours'), '210')
  await user.type(screen.getByLabelText('SPA Hours'), '90')
  await user.click(screen.getByRole('button', { name: 'Apply Entitlement' }))

  expect(onSubmit).toHaveBeenCalledWith({
    mode: 'manual',
    other_hours: '0',
    dcc_hours: '210',
    spa_hours: '90',
    reason: null,
  })
})

it('keeps API decimal noise out of editable entitlement fields', () => {
  const workspace: EntitlementWorkspace = {
    recommendation: null,
    application: {
      id: 1,
      leave_year_id: 2,
      recommendation_id: null,
      mode: 'manual',
      entitlement: {
        dcc_hours: '203.3040000000000000000000000',
        spa_hours: '88.06400000000000000000000003',
        other_hours: '0',
        total_hours: '291.3680000000000000000000000',
      },
      reason: 'Trust-approved values',
      updated_at: '2026-08-12T10:00:00',
    },
  }

  render(
    <EntitlementForm
      initialValue={workspace}
      busy={false}
      onPreview={vi.fn()}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
    />,
  )

  expect(screen.getByLabelText('DCC Hours')).toHaveValue(203.304)
  expect(screen.getByLabelText('SPA Hours')).toHaveValue(88.064)
})

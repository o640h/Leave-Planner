import { fireEvent, render, screen } from '@testing-library/react'
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
    consultant_appointment_date: '2010-01-01',
    consultant_service_start_date: '2010-01-01',
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

  fireEvent.change(screen.getByLabelText('Appointment Date'), {
    target: { value: '2010-01-01' },
  })
  fireEvent.change(screen.getByLabelText('Reckonable Service Start'), {
    target: { value: '2010-01-01' },
  })
  await user.click(screen.getByRole('button', { name: 'Preview Recommendation' }))

  expect(onPreview).toHaveBeenCalledWith('2010-01-01', '2010-01-01')
  expect(await screen.findByText('291.368')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Apply Entitlement' }))
  expect(onSubmit).toHaveBeenCalledWith({
    mode: 'calculated',
    other_hours: '0',
    consultant_appointment_date: '2010-01-01',
    consultant_service_start_date: '2010-01-01',
  })
})

it('requires an explanation when the operator enters manual values', async () => {
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

  expect(screen.getByRole('alert')).toHaveTextContent('Explain the manually applied values.')
  expect(onSubmit).not.toHaveBeenCalled()

  await user.type(screen.getByLabelText('Reason'), 'Trust-approved starting values')
  await user.click(screen.getByRole('button', { name: 'Apply Entitlement' }))

  expect(onSubmit).toHaveBeenCalledWith({
    mode: 'manual',
    other_hours: '0',
    dcc_hours: '210',
    spa_hours: '90',
    reason: 'Trust-approved starting values',
  })
})

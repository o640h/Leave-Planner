import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { RemovalDialog } from './RemovalDialog'

const impact = {
  resource_name: '29 Aug 2025 - 28 Aug 2026',
  action: 'delete' as const,
  confirmation_text: 'DELETE',
  consequences: ['Two job plans will be deleted.', 'Audit history will be retained.'],
  can_proceed: true,
  blocking_reason: null,
}

it('requires the exact impact confirmation before deleting', async () => {
  const user = userEvent.setup()
  const confirm = vi.fn()

  render(
    <RemovalDialog
      title="Delete Leave Year"
      impact={impact}
      busy={false}
      error={null}
      onConfirm={confirm}
      onCancel={vi.fn()}
    />,
  )

  // The impact is visible before the destructive action becomes available.
  expect(screen.getByText('Two job plans will be deleted.')).toBeInTheDocument()
  const deleteButton = screen.getByRole('button', { name: 'Delete' })
  expect(deleteButton).toBeDisabled()

  await user.type(screen.getByRole('textbox'), 'DELETE')
  expect(deleteButton).toBeEnabled()
  await user.click(deleteButton)

  expect(confirm).toHaveBeenCalledWith('DELETE')
})

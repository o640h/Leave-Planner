import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AccountDialog, AccountPage } from './AccountPage'

const account = {
  public_id: '0123456789abcdef0123456789abcdef',
  display_name: 'Primary Operator',
  display_email: 'operator@example.org',
}

describe('account page', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the signed-in identity separately from security actions', async () => {
    const user = userEvent.setup()
    render(<AccountPage user={account} />)

    expect(screen.getByRole('heading', { name: 'Account' })).toBeInTheDocument()
    expect(screen.getByText('Primary Operator')).toBeInTheDocument()
    expect(screen.getByText('operator@example.org')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Change Email' }))
    const dialog = screen.getByRole('dialog', { name: 'Change Email' })
    expect(within(dialog).getByText('Current email: operator@example.org')).toBeInTheDocument()

    await user.click(within(dialog).getByLabelText('New Email'))
    expect(screen.getByRole('dialog', { name: 'Change Email' })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Change Email' })).not.toBeInTheDocument()
  })

  it('dismisses Change Email only when the backdrop itself is pressed', async () => {
    const user = userEvent.setup()
    const { container } = render(<AccountPage user={account} />)

    await user.click(screen.getByRole('button', { name: 'Change Email' }))
    const backdrop = container.querySelector('.modal-backdrop')
    expect(backdrop).not.toBeNull()
    fireEvent.mouseDown(backdrop as Element)

    expect(screen.queryByRole('dialog', { name: 'Change Email' })).not.toBeInTheDocument()
  })

  it('keeps Change Email open while a request is being submitted', async () => {
    const user = userEvent.setup()
    let completeRequest: ((response: unknown) => void) | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise((resolve) => {
            completeRequest = resolve
          }),
      ),
    )
    const { container } = render(<AccountPage user={account} />)

    await user.click(screen.getByRole('button', { name: 'Change Email' }))
    await user.type(screen.getByLabelText('New Email'), 'new@example.org')
    await user.type(screen.getByLabelText('Current Password'), 'current-password')
    await user.click(screen.getByRole('button', { name: 'Send Confirmation' }))

    expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled()
    await user.keyboard('{Escape}')
    fireEvent.mouseDown(container.querySelector('.modal-backdrop') as Element)
    expect(screen.getByRole('dialog', { name: 'Change Email' })).toBeInTheDocument()

    completeRequest?.({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: () => Promise.resolve({ message: 'Check the new address for a confirmation link.' }),
    })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close' })).toBeEnabled())
  })

  it('closes only Change Email when its backdrop is pressed over Account', async () => {
    const user = userEvent.setup()
    render(
      <main className="application-content">
        <AccountDialog user={account} onClose={vi.fn()} />
      </main>,
    )

    await user.click(screen.getByRole('button', { name: 'Change Email' }))
    const changeEmail = screen.getByRole('dialog', { name: 'Change Email' })
    fireEvent.mouseDown(changeEmail.closest('.modal-backdrop') as Element)

    expect(screen.queryByRole('dialog', { name: 'Change Email' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Account' })).toBeInTheDocument()
  })
})

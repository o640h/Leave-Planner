import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'

function json(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: () => Promise.resolve(body),
  }
}

const account = {
  public_id: '0123456789abcdef0123456789abcdef',
  display_name: 'Primary Operator',
  display_email: 'operator@example.org',
}

describe('account recovery screens', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.history.replaceState({}, '', '/')
    document.cookie = 'leave_planner_csrf=; Max-Age=0; Path=/'
  })

  it('requests a password reset without revealing account existence', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') return json({ authenticated: false, user: null })
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/auth/password-reset/request') {
          expect(JSON.parse(options.body as string)).toEqual({ email: 'operator@example.org' })
          return json({
            message: 'If the address can use this action, an email will arrive with the next step.',
          })
        }
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Forgot Password' }))
    await user.type(screen.getByLabelText('Email'), 'operator@example.org')
    await user.click(screen.getByRole('button', { name: 'Send Link' }))
    expect(await screen.findByText(/If the address can use this action/)).toBeInTheDocument()
  })

  it('uses a reset link once and returns to sign in', async () => {
    const user = userEvent.setup()
    window.history.replaceState(
      {},
      '',
      '/?action=reset-password&token=secure-reset-token-value-123456',
    )
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') return json({ authenticated: false, user: null })
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/auth/password-reset/confirm') {
          expect(JSON.parse(options.body as string)).toEqual({
            token: 'secure-reset-token-value-123456',
            password: 'eight888',
          })
          return json({ message: 'Password changed. Sign in with your new password.' })
        }
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Choose New Password' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('New Password'), 'eight888')
    await user.type(screen.getByLabelText('Confirm New Password'), 'eight888')
    await user.click(screen.getByRole('button', { name: 'Change Password' }))
    expect(await screen.findByText(/Password changed/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back To Sign In' }))
    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('lets an authenticated account request an email change with its password', async () => {
    const user = userEvent.setup()
    document.cookie = 'leave_planner_csrf=csrf-value; Path=/'
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          return json({
            authenticated: true,
            user: account,
            workspace: {
              state: 'active',
              active_workspace_id: 1,
              memberships: [
                {
                  workspace_id: 1,
                  workspace_name: 'Radiology',
                  role: 'owner',
                  linked_consultant_id: null,
                },
              ],
            },
          })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants') return json([])
        if (path === '/api/auth/email-change/request') {
          expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('csrf-value')
          expect(JSON.parse(options.body as string)).toEqual({
            email: 'new@example.org',
            password: 'current-password',
          })
          return json({ message: 'Check the new address for a confirmation link.' })
        }
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Account' }))
    expect(screen.getByRole('heading', { name: 'Account' })).toBeInTheDocument()
    expect(screen.getByText('Primary Operator')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Change Email' }))
    expect(screen.getByText('Current email: operator@example.org')).toBeInTheDocument()
    await user.type(screen.getByLabelText('New Email'), 'new@example.org')
    await user.type(screen.getByLabelText('Current Password'), 'current-password')
    await user.click(screen.getByRole('button', { name: 'Send Confirmation' }))
    expect(await screen.findByText(/Check the new address/)).toBeInTheDocument()
  })
})

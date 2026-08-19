import { render, screen, waitFor } from '@testing-library/react'
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

describe('shared Admin authentication', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.cookie = 'leave_planner_csrf=; Max-Age=0; Path=/'
  })

  it('shows password-only sign in, reports rejection, and loads the workspace', async () => {
    const user = userEvent.setup()
    let authenticated = false

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          return json({ authenticated: false, user: null })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/auth/login') {
          const body = JSON.parse(options.body as string) as { password: string }
          if (body.password !== 'correct-password') {
            return json(
              {
                error: {
                  code: 'invalid_credentials',
                  message: 'Sign in could not be completed. Check the password and try again.',
                },
              },
              401,
            )
          }
          authenticated = true
          return json({ authenticated: true, user: { id: 1, display_name: 'Admin' } })
        }
        if (path === '/api/consultants' && authenticated) return json([])
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('Enter the Admin password.')).toBeInTheDocument()

    const password = screen.getByLabelText('Password')
    await user.type(password, 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText(/Check the password and try again/)).toBeInTheDocument()

    await user.clear(password)
    await user.type(password, 'correct-password')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByRole('heading', { name: 'Consultants' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument()
  })

  it('sends the readable CSRF cookie on sign out and returns to sign in', async () => {
    const user = userEvent.setup()
    document.cookie = 'leave_planner_csrf=csrf-value; Path=/'

    const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = input.toString()
      if (path === '/api/auth/session') {
        return json({ authenticated: true, user: { id: 1, display_name: 'Admin' } })
      }
      if (path === '/api/health') return json({ status: 'ok' })
      if (path === '/api/consultants') return json([])
      if (path === '/api/auth/logout') {
        const headers = new Headers(options.headers)
        expect(options.credentials).toBe('same-origin')
        expect(headers.get('X-CSRF-Token')).toBe('csrf-value')
        return json({ authenticated: false, user: null })
      }
      throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Sign Out' }))
    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/auth/logout',
        expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
      ),
    )
  })
})

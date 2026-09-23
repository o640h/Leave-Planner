import { render, screen, waitFor, within } from '@testing-library/react'
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
  display_email: 'Operator@Example.org',
}

const activeWorkspace = {
  state: 'active',
  active_workspace_id: 1,
  memberships: [
    {
      workspace_id: 1,
      workspace_name: 'Clinical Services',
      role: 'owner',
      linked_consultant_id: null,
    },
  ],
}

describe('email account authentication', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.cookie = 'leave_planner_csrf=; Max-Age=0; Path=/'
  })

  it('validates email sign in, reports a generic rejection, and loads the workspace', async () => {
    const user = userEvent.setup()
    let authenticated = false

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') return json({ authenticated: false, user: null })
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/auth/login') {
          const body = JSON.parse(options.body as string) as {
            email: string
            password: string
          }
          expect(body.email).toBe('Operator@Example.org')
          if (body.password !== 'correct-password') {
            return json(
              {
                error: {
                  code: 'invalid_credentials',
                  message: 'The email or password is incorrect.',
                },
              },
              401,
            )
          }
          authenticated = true
          return json({ authenticated: true, user: account, workspace: activeWorkspace })
        }
        if (path === '/api/consultants' && authenticated) return json([])
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByText('Merydio')).toBeInTheDocument()
    expect(screen.getByText('Secure Account')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verify Email' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Email'), 'Operator@Example.org')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('Enter your password.')).toBeInTheDocument()

    const password = screen.getByLabelText('Password')
    await user.type(password, 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('The email or password is incorrect.')).toBeInTheDocument()

    await user.clear(password)
    await user.paste('correct-password')
    await user.click(screen.getByRole('button', { name: 'Show' }))
    expect(password).toHaveAttribute('type', 'text')
    await user.click(screen.getByRole('button', { name: 'Hide' }))
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    expect(await screen.findByRole('heading', { name: 'Consultants' })).toBeInTheDocument()
    const accountButton = screen.getByRole('button', { name: 'Account' })
    await user.click(accountButton)
    expect(screen.getByRole('dialog', { name: 'Account' })).toBeInTheDocument()
    await user.click(accountButton)
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Account' })).not.toBeInTheDocument(),
    )
  })

  it('sends the readable CSRF cookie on sign out and returns to sign in', async () => {
    const user = userEvent.setup()
    document.cookie = 'leave_planner_csrf=csrf-value; Path=/'

    const fetchMock = vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      const path = input.toString()
      if (path === '/api/auth/session') {
        return json({ authenticated: true, user: account, workspace: activeWorkspace })
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

  it('explains an expired session before asking the person to sign in again', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          return json({ authenticated: true, user: account, workspace: activeWorkspace })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants') {
          return json(
            { error: { code: 'authentication_required', message: 'Sign in is required' } },
            401,
          )
        }
        throw new Error(`Unexpected request: GET ${path}`)
      }),
    )

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByText('Your session expired. Sign in again to continue.')).toBeInTheDocument()
  })

  it('shows onboarding when a signed-in account has no membership', async () => {
    const user = userEvent.setup()
    let workspaceCreated = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          return json({
            authenticated: true,
            user: account,
            workspace: { state: 'onboarding', active_workspace_id: null, memberships: [] },
          })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/workspaces' && options.method === 'POST') {
          expect(JSON.parse(options.body as string)).toEqual({ name: 'Radiology' })
          workspaceCreated = true
          return json(activeWorkspace)
        }
        if (path === '/api/consultants') {
          if (workspaceCreated) return json([])
          return json({ error: { code: 'workspace_access_denied', message: 'Access denied' } }, 403)
        }
        throw new Error(`Unexpected request: GET ${path}`)
      }),
    )

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'No Workspace Yet' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Change Email' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Workspace' })).toBeInTheDocument()
    expect(
      screen.getByText(
        'This account does not currently belong to a workspace. You can create one now or sign out.',
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Create Workspace' }))
    const dialog = screen.getByRole('dialog', { name: 'Create Workspace' })
    await user.click(within(dialog).getByRole('button', { name: 'Create Workspace' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a workspace name.')
    await user.type(screen.getByLabelText('Workspace Name'), 'Radiology')
    await user.click(within(dialog).getByRole('button', { name: 'Create Workspace' }))
    expect(await screen.findByRole('heading', { name: 'Consultants' })).toBeInTheDocument()
  })

  it('offers account creation only when registration is open', async () => {
    const user = userEvent.setup()

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') return json({ authenticated: false, user: null })
        if (path === '/api/auth/registration' && !options.method) return json({ mode: 'open' })
        if (path === '/api/auth/registration' && options.method === 'POST') {
          expect(JSON.parse(options.body as string)).toEqual({
            display_name: 'Alex Morgan',
            email: 'alex@example.org',
            password: 'password8',
          })
          return json({ message: 'Check your email for the next account-creation step.' })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Create Account' }))
    expect(screen.getByRole('heading', { name: 'Create Account' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Name'), 'Alex Morgan')
    await user.type(screen.getByLabelText('Email'), 'alex@example.org')
    await user.type(screen.getByLabelText('Password'), 'password8')
    await user.type(screen.getByLabelText('Confirm Password'), 'password8')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))
    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(
      screen.getByText('Check your email for the next account-creation step.'),
    ).toBeInTheDocument()
  })

  it('requires an explicit workspace choice and opens the selected workspace', async () => {
    const user = userEvent.setup()
    const selectionRequired = {
      state: 'selection_required',
      active_workspace_id: null,
      memberships: [
        ...activeWorkspace.memberships,
        {
          workspace_id: 2,
          workspace_name: 'Second Workspace',
          role: 'admin',
          linked_consultant_id: null,
        },
      ],
    }

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          return json({ authenticated: true, user: account, workspace: selectionRequired })
        }
        if (path === '/api/workspaces/active') {
          expect(JSON.parse(options.body as string)).toEqual({ workspace_id: 2 })
          return json({ ...selectionRequired, state: 'active', active_workspace_id: 2 })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        if (path === '/api/consultants') return json([])
        throw new Error(`Unexpected request: ${options.method ?? 'GET'} ${path}`)
      }),
    )

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Choose Workspace' })).toBeInTheDocument()
    await user.click(screen.getByRole('combobox', { name: 'Choose Workspace' }))
    await user.click(screen.getByRole('option', { name: /Second Workspace/ }))
    expect(await screen.findByRole('heading', { name: 'Consultants' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Switch Workspace' }))
    expect(screen.getByRole('button', { name: /Second Workspace.*Open/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await user.click(screen.getByRole('button', { name: 'Switch Workspace' }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Choose Workspace' })).not.toBeInTheDocument(),
    )
  })

  it('offers a retry when the server is initially unavailable', async () => {
    const user = userEvent.setup()
    let available = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = input.toString()
        if (path === '/api/auth/session') {
          if (!available) throw new TypeError('Failed to fetch')
          return json({ authenticated: false, user: null })
        }
        if (path === '/api/health') return json({ status: 'ok' })
        throw new Error(`Unexpected request: GET ${path}`)
      }),
    )

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Server Unavailable' })).toBeInTheDocument()
    available = true
    await user.click(screen.getByRole('button', { name: 'Try Again' }))
    expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
  })
})

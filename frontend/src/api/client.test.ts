import { afterEach, expect, it, vi } from 'vitest'

import {
  apiRequest,
  ApiClientError,
  AUTHENTICATION_REQUIRED_EVENT,
  AUTHORIZATION_DENIED_EVENT,
  operatorErrorMessage,
  rememberWorkspaceRevision,
  SERVICE_UNAVAILABLE_EVENT,
} from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('shows the useful field reason from an API validation response', () => {
  const error = new ApiClientError(422, 'validation_error', 'Request validation failed', [
    {
      loc: ['body', 'cycle_anchor_date'],
      msg: 'Value error, The cycle anchor cannot be after Effective From',
    },
  ])

  expect(operatorErrorMessage(error)).toBe(
    'cycle anchor date: The cycle anchor cannot be after Effective From',
  )
})

it.each([
  [401, 'authentication_required', AUTHENTICATION_REQUIRED_EVENT],
  [403, 'workspace_access_denied', AUTHORIZATION_DENIED_EVENT],
  [503, 'service_unavailable', SERVICE_UNAVAILABLE_EVENT],
])('reports application state for an HTTP %i response', async (status, code, eventName) => {
  const listener = vi.fn()
  window.addEventListener(eventName, listener, { once: true })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      json: () => Promise.resolve({ error: { code, message: 'Failed' } }),
    }),
  )

  await expect(apiRequest('/api/consultants')).rejects.toBeInstanceOf(ApiClientError)
  expect(listener).toHaveBeenCalledOnce()
})

it('does not misreport a CSRF rejection as missing workspace access', async () => {
  const listener = vi.fn()
  window.addEventListener(AUTHORIZATION_DENIED_EVENT, listener, { once: true })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () =>
        Promise.resolve({
          error: { code: 'csrf_failed', message: 'Request could not be verified' },
        }),
    }),
  )

  await expect(apiRequest('/api/auth/login')).rejects.toMatchObject({ code: 'csrf_failed' })
  expect(listener).not.toHaveBeenCalled()
})

it('reports a server outage when fetch cannot connect', async () => {
  const listener = vi.fn()
  window.addEventListener(SERVICE_UNAVAILABLE_EVENT, listener, { once: true })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

  await expect(apiRequest('/api/consultants')).rejects.toThrow('Failed to fetch')
  expect(listener).toHaveBeenCalledOnce()
})

it('sends the last workspace revision with shared writes', async () => {
  rememberWorkspaceRevision(12)
  const request = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ 'X-Workspace-Revision': '13' }),
    json: () => Promise.resolve({}),
  })
  vi.stubGlobal('fetch', request)

  await apiRequest('/api/consultants', { method: 'POST', body: '{}' })

  const options = request.mock.calls[0][1] as RequestInit
  expect(new Headers(options.headers).get('If-Match')).toBe('12')
})

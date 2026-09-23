type ErrorEnvelope = {
  error?: {
    code?: unknown
    message?: unknown
    details?: unknown
  }
}

export const AUTHENTICATION_REQUIRED_EVENT = 'leave-planner:authentication-required'
export const AUTHORIZATION_DENIED_EVENT = 'leave-planner:authorization-denied'
export const SERVICE_UNAVAILABLE_EVENT = 'leave-planner:service-unavailable'
export const WORKSPACE_INVALIDATED_EVENT = 'leave-planner:workspace-invalidated'

const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const unavailableStatuses = new Set([502, 503, 504])
let workspaceRevision: number | null = null

export function rememberWorkspaceRevision(revision: unknown): void {
  if (typeof revision === 'number' && Number.isInteger(revision) && revision > 0) {
    workspaceRevision = revision
  }
}

function rememberResponseRevision(response: Response, body: unknown): void {
  const header = response.headers?.get?.('X-Workspace-Revision')
  if (header) rememberWorkspaceRevision(Number(header))
  if (typeof body !== 'object' || body === null) return
  const record = body as { revision?: unknown; workspace?: { revision?: unknown } | null }
  rememberWorkspaceRevision(record.revision)
  rememberWorkspaceRevision(record.workspace?.revision)
}

function cookieValue(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`
  const match = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return match ? decodeURIComponent(match.slice(prefix.length)) : null
}

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function requestError(
  response: Response,
): Promise<{ error: ApiClientError; hasErrorEnvelope: boolean }> {
  const body = (await response.json().catch(() => null)) as ErrorEnvelope | null
  const hasErrorEnvelope = typeof body?.error === 'object' && body.error !== null
  const code = typeof body?.error?.code === 'string' ? body.error.code : 'request_failed'
  const message =
    typeof body?.error?.message === 'string'
      ? body.error.message
      : 'The request could not be completed.'
  return {
    error: new ApiClientError(response.status, code, message, body?.error?.details),
    hasErrorEnvelope,
  }
}

function reportApplicationState(
  response: Response,
  path: string,
  code: string,
  hasErrorEnvelope: boolean,
): void {
  if (response.status === 401 && path !== '/api/auth/login') {
    window.dispatchEvent(new Event(AUTHENTICATION_REQUIRED_EVENT))
  } else if (response.status === 403 && code === 'workspace_access_denied') {
    window.dispatchEvent(new Event(AUTHORIZATION_DENIED_EVENT))
  } else if (
    code === 'service_unavailable' ||
    (!hasErrorEnvelope && unavailableStatuses.has(response.status))
  ) {
    window.dispatchEvent(new Event(SERVICE_UNAVAILABLE_EVENT))
  }
}

async function fetchFromApplication(path: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(path, options)
  } catch (error) {
    window.dispatchEvent(new Event(SERVICE_UNAVAILABLE_EVENT))
    throw error
  }
}

export async function apiRequest<ResponseBody>(
  path: string,
  options: RequestInit = {},
): Promise<ResponseBody> {
  const headers = new Headers(options.headers)

  if (options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const method = (options.method ?? 'GET').toUpperCase()
  const csrfToken = cookieValue(
    window.location.protocol === 'https:' ? '__Host-csrf' : 'leave_planner_csrf',
  )
  if (unsafeMethods.has(method) && csrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  if (unsafeMethods.has(method) && workspaceRevision && !headers.has('If-Match')) {
    headers.set('If-Match', String(workspaceRevision))
  }

  const response = await fetchFromApplication(path, {
    ...options,
    credentials: 'same-origin',
    headers,
  })

  if (!response.ok) {
    const { error, hasErrorEnvelope } = await requestError(response)
    reportApplicationState(response, path, error.code, hasErrorEnvelope)
    if (error.code === 'stale_workspace_data') {
      window.dispatchEvent(
        new CustomEvent(WORKSPACE_INVALIDATED_EVENT, {
          detail: { revision: null, scopes: ['all'] },
        }),
      )
    }
    throw error
  }

  const body = (await response.json()) as ResponseBody
  rememberResponseRevision(response, body)
  return body
}

export async function apiFileRequest(
  path: string,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetchFromApplication(path, { credentials: 'same-origin' })
  if (!response.ok) {
    const { error, hasErrorEnvelope } = await requestError(response)
    reportApplicationState(response, path, error.code, hasErrorEnvelope)
    throw error
  }

  const disposition = response.headers.get('Content-Disposition')
  const filename = disposition?.match(/filename="([^"]+)"/i)?.[1] ?? null
  return { blob: await response.blob(), filename }
}

export function operatorErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.code === 'validation_error' && Array.isArray(error.details)) {
      const first = error.details.find(
        (detail): detail is { loc?: unknown; msg: string } =>
          typeof detail === 'object' &&
          detail !== null &&
          typeof (detail as { msg?: unknown }).msg === 'string',
      )

      if (first) {
        const location = Array.isArray(first.loc)
          ? first.loc
              .filter((part) => part !== 'body' && typeof part === 'string')
              .map((part) => part.replaceAll('_', ' '))
              .join(' / ')
          : ''
        const message = first.msg.replace(/^Value error,\s*/i, '')
        return location ? `${location}: ${message}` : message
      }
    }

    return error.message
  }

  return 'The server could not be reached. Please try again.'
}

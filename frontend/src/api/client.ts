type ErrorEnvelope = {
  error?: {
    code?: unknown
    message?: unknown
    details?: unknown
  }
}

export const AUTHENTICATION_REQUIRED_EVENT = 'leave-planner:authentication-required'

const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

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

async function requestError(response: Response): Promise<ApiClientError> {
  const body = (await response.json().catch(() => null)) as ErrorEnvelope | null
  const code = typeof body?.error?.code === 'string' ? body.error.code : 'request_failed'
  const message =
    typeof body?.error?.message === 'string'
      ? body.error.message
      : 'The request could not be completed.'
  return new ApiClientError(response.status, code, message, body?.error?.details)
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

  const response = await fetch(path, {
    ...options,
    credentials: 'same-origin',
    headers,
  })

  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login') {
      window.dispatchEvent(new Event(AUTHENTICATION_REQUIRED_EVENT))
    }
    throw await requestError(response)
  }

  return response.json() as Promise<ResponseBody>
}

export async function apiFileRequest(
  path: string,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(path, { credentials: 'same-origin' })
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new Event(AUTHENTICATION_REQUIRED_EVENT))
    }
    throw await requestError(response)
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

  return 'The local service could not be reached. Please try again.'
}

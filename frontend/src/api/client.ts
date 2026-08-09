type ErrorEnvelope = {
  error?: {
    code?: unknown
    message?: unknown
    details?: unknown
  }
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

export async function apiRequest<ResponseBody>(
  path: string,
  options: RequestInit = {},
): Promise<ResponseBody> {
  const headers = new Headers(options.headers)

  if (options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ErrorEnvelope | null

    const code = typeof body?.error?.code === 'string' ? body.error.code : 'request_failed'
    const message =
      typeof body?.error?.message === 'string'
        ? body.error.message
        : 'The request could not be completed.'

    throw new ApiClientError(response.status, code, message, body?.error?.details)
  }

  return response.json() as Promise<ResponseBody>
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
              .join(' · ')
          : ''
        const message = first.msg.replace(/^Value error,\s*/i, '')
        return location ? `${location}: ${message}` : message
      }
    }

    return error.message
  }

  return 'The local service could not be reached. Please try again.'
}

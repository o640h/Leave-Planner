import { apiRequest } from '../api/client'
import type { Session } from './types'

export const getSession = () => apiRequest<Session>('/api/auth/session')

export const login = (email: string, password: string) =>
  apiRequest<Session>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const logout = () => apiRequest<Session>('/api/auth/logout', { method: 'POST' })

export const confirmEmailVerification = (token: string) =>
  apiRequest<{ message: string }>('/api/auth/verification/confirm', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })

export const requestPasswordReset = (email: string) =>
  apiRequest<{ message: string }>('/api/auth/password-reset/request', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })

export const confirmPasswordReset = (token: string, password: string) =>
  apiRequest<{ message: string }>('/api/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  })

export const requestEmailChange = (email: string, password: string) =>
  apiRequest<{ message: string }>('/api/auth/email-change/request', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const confirmEmailChange = (token: string) =>
  apiRequest<{ message: string }>('/api/auth/email-change/confirm', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })

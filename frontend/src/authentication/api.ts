import { apiRequest } from '../api/client'
import type { Session } from './types'

export const getSession = () => apiRequest<Session>('/api/auth/session')

export const login = (password: string) =>
  apiRequest<Session>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })

export const logout = () => apiRequest<Session>('/api/auth/logout', { method: 'POST' })

import { apiRequest } from '../api/client'
import type { RegistrationConfiguration, Session } from './types'

export const getSession = () => apiRequest<Session>('/api/auth/session')

export const login = (email: string, password: string) =>
  apiRequest<Session>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const logout = () => apiRequest<Session>('/api/auth/logout', { method: 'POST' })

export const getRegistrationConfiguration = () =>
  apiRequest<RegistrationConfiguration>('/api/auth/registration')

export const registerAccount = (
  displayName: string,
  email: string,
  password: string,
  invitationToken?: string,
) =>
  apiRequest<{ message: string }>('/api/auth/registration', {
    method: 'POST',
    body: JSON.stringify({
      display_name: displayName,
      email,
      password,
      invitation_token: invitationToken,
    }),
  })

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

export const changePassword = (
  currentPassword: string,
  password: string,
  passwordConfirmation: string,
) =>
  apiRequest<{ message: string }>('/api/auth/password-change', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      password,
      password_confirmation: passwordConfirmation,
    }),
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

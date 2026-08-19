export type AuthenticatedUser = {
  id: number
  display_name: string
}

export type Session = {
  authenticated: boolean
  user: AuthenticatedUser | null
}

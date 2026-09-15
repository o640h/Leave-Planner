export type AuthenticatedUser = {
  public_id: string
  display_name: string
  display_email: string
}

export type Session = {
  authenticated: boolean
  user: AuthenticatedUser | null
}

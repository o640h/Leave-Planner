export type RemovalImpact = {
  resource_name: string
  action: 'archive' | 'delete'
  confirmation_text: string
  consequences: string[]
  can_proceed: boolean
  blocking_reason: string | null
}

export type RemovalResult = {
  message: string
  entitlement_status:
    'not_applicable' | 'not_configured' | 'preserved' | 'refreshed' | 'needs_attention'
}

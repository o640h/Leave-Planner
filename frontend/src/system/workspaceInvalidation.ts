import { useEffect, useRef } from 'react'

import { WORKSPACE_INVALIDATED_EVENT } from '../api/client'

export type InvalidationDetail = {
  revision: number | null
  scopes: string[]
}

export function dispatchInvalidation(detail: InvalidationDetail): void {
  window.dispatchEvent(new CustomEvent(WORKSPACE_INVALIDATED_EVENT, { detail }))
}

export function useWorkspaceInvalidation(scopes: readonly string[], callback: () => void): void {
  const callbackRef = useRef(callback)
  const scopeKey = scopes.join('|')

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    const acceptedScopes = new Set(scopeKey.split('|'))
    function invalidated(event: Event) {
      const detail = (event as CustomEvent<InvalidationDetail>).detail
      if (
        detail.scopes.includes('all') ||
        detail.scopes.some((scope) => acceptedScopes.has(scope))
      ) {
        callbackRef.current()
      }
    }
    window.addEventListener(WORKSPACE_INVALIDATED_EVENT, invalidated)
    return () => window.removeEventListener(WORKSPACE_INVALIDATED_EVENT, invalidated)
  }, [scopeKey])
}

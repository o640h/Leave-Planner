import { useEffect } from 'react'

import { rememberWorkspaceRevision } from '../api/client'
import { dispatchInvalidation } from './workspaceInvalidation'

type WorkspaceInvalidationMessage = {
  type: 'workspace_invalidated'
  revision: number
  scopes: string[]
}

function isInvalidationMessage(value: unknown): value is WorkspaceInvalidationMessage {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<WorkspaceInvalidationMessage>
  return (
    candidate.type === 'workspace_invalidated' &&
    typeof candidate.revision === 'number' &&
    Array.isArray(candidate.scopes) &&
    candidate.scopes.every((scope) => typeof scope === 'string')
  )
}

export function WorkspaceUpdateConnection({ workspaceId }: { workspaceId: number }) {
  useEffect(() => {
    if (typeof WebSocket === 'undefined') return
    let active = true
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let reconnectDelay = 1000

    function connect() {
      if (!active) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/api/workspace-updates`)
      socket.addEventListener('open', () => {
        reconnectDelay = 1000
        dispatchInvalidation({ revision: null, scopes: ['all'] })
      })
      socket.addEventListener('message', (event) => {
        let parsed: unknown
        try {
          parsed = JSON.parse(String(event.data))
        } catch {
          return
        }
        if (!isInvalidationMessage(parsed)) return
        rememberWorkspaceRevision(parsed.revision)
        dispatchInvalidation({ revision: parsed.revision, scopes: parsed.scopes })
      })
      socket.addEventListener('close', (event) => {
        socket = null
        if (!active || event.code === 4401 || event.code === 4403) return
        reconnectTimer = window.setTimeout(connect, reconnectDelay)
        reconnectDelay = Math.min(reconnectDelay * 2, 30_000)
      })
    }

    connect()
    return () => {
      active = false
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [workspaceId])

  return null
}

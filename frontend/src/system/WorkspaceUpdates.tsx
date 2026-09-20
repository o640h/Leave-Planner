import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { rememberWorkspaceRevision } from '../api/client'
import {
  WorkspacePointerContext,
  type RemotePointer,
  type WorkspacePointerContextValue,
} from './workspacePointers'
import { dispatchInvalidation } from './workspaceInvalidation'

type WorkspaceInvalidationMessage = {
  type: 'workspace_invalidated'
  revision: number
  scopes: string[]
}

type PointerUpdatedMessage = {
  type: 'pointer_updated'
  connection_id: string
  label: string
  colour_index: number
  view: string
  x: number
  y: number
}

type PointerRemovedMessage = { type: 'pointer_removed'; connection_id: string }

const POINTER_INTERVAL_MS = 50
const HEARTBEAT_INTERVAL_MS = 15_000
const CONNECTION_TIMEOUT_MS = 3_000
const MAX_RECONNECT_DELAY_MS = 5_000

function pointerStorageKey(workspaceId: number, view: string): string {
  return `leave-planner:pointer:${workspaceId}:${view}`
}

function storedPointer(workspaceId: number, view: string): { x: number; y: number } | null {
  try {
    const raw = window.sessionStorage.getItem(pointerStorageKey(workspaceId, view))
    if (!raw) return null
    const value = JSON.parse(raw) as { x?: unknown; y?: unknown }
    if (
      typeof value.x !== 'number' ||
      typeof value.y !== 'number' ||
      value.x < 0 ||
      value.x > 1 ||
      value.y < 0 ||
      value.y > 1
    ) {
      return null
    }
    return { x: value.x, y: value.y }
  } catch {
    return null
  }
}

function rememberPointer(workspaceId: number, view: string, x: number, y: number): void {
  try {
    window.sessionStorage.setItem(pointerStorageKey(workspaceId, view), JSON.stringify({ x, y }))
  } catch {
    // Pointer persistence is only a refresh convenience; live updates can continue without it.
  }
}

function forgetPointer(workspaceId: number, view: string): void {
  try {
    window.sessionStorage.removeItem(pointerStorageKey(workspaceId, view))
  } catch {
    // Ignore unavailable browser storage and still hide the live pointer.
  }
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

function isPointerUpdated(value: unknown): value is PointerUpdatedMessage {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<PointerUpdatedMessage>
  return (
    candidate.type === 'pointer_updated' &&
    typeof candidate.connection_id === 'string' &&
    typeof candidate.label === 'string' &&
    typeof candidate.colour_index === 'number' &&
    typeof candidate.view === 'string' &&
    typeof candidate.x === 'number' &&
    typeof candidate.y === 'number'
  )
}

function isPointerRemoved(value: unknown): value is PointerRemovedMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as Partial<PointerRemovedMessage>).type === 'pointer_removed' &&
    typeof (value as Partial<PointerRemovedMessage>).connection_id === 'string'
  )
}

export function WorkspaceUpdateProvider({
  workspaceId,
  children,
}: {
  workspaceId: number
  children: ReactNode
}) {
  const [pointers, setPointers] = useState<RemotePointer[]>([])
  const socketRef = useRef<WebSocket | null>(null)
  const viewRef = useRef<string | null>(null)
  const pendingPointerRef = useRef<{ view: string; x: number; y: number } | null>(null)
  const pointerTimerRef = useRef<number | null>(null)
  const lastPointerSentRef = useRef(0)

  const send = useCallback((payload: object) => {
    const socket = socketRef.current
    if (socket?.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(payload))
    return true
  }, [])

  const flushPointer = useCallback(() => {
    pointerTimerRef.current = null
    const pointer = pendingPointerRef.current
    if (!pointer) return
    if (!send({ type: 'pointer', ...pointer })) return
    pendingPointerRef.current = null
    lastPointerSentRef.current = performance.now()
  }, [send])

  const setView = useCallback(
    (view: string | null) => {
      if (viewRef.current === view) return
      viewRef.current = view
      pendingPointerRef.current = null
      if (pointerTimerRef.current !== null) {
        window.clearTimeout(pointerTimerRef.current)
        pointerTimerRef.current = null
      }
      setPointers([])
      send({ type: 'view', view })
      if (view) {
        const restored = storedPointer(workspaceId, view)
        if (restored) {
          pendingPointerRef.current = { view, ...restored }
          flushPointer()
        }
      }
    },
    [flushPointer, send, workspaceId],
  )

  const movePointer = useCallback(
    (view: string, x: number, y: number) => {
      if (viewRef.current !== view) return
      pendingPointerRef.current = { view, x, y }
      rememberPointer(workspaceId, view, x, y)
      if (pointerTimerRef.current !== null) return
      const elapsed = performance.now() - lastPointerSentRef.current
      if (elapsed >= POINTER_INTERVAL_MS) {
        flushPointer()
      } else {
        pointerTimerRef.current = window.setTimeout(flushPointer, POINTER_INTERVAL_MS - elapsed)
      }
    },
    [flushPointer, workspaceId],
  )

  const hidePointer = useCallback(() => {
    pendingPointerRef.current = null
    if (pointerTimerRef.current !== null) {
      window.clearTimeout(pointerTimerRef.current)
      pointerTimerRef.current = null
    }
    if (viewRef.current) forgetPointer(workspaceId, viewRef.current)
    send({ type: 'pointer_hidden' })
  }, [send, workspaceId])

  useEffect(() => {
    if (typeof WebSocket === 'undefined') return
    let active = true
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let heartbeatTimer: number | null = null
    let connectionTimer: number | null = null
    let reconnectDelay = 1000

    function connect() {
      if (!active) return
      reconnectTimer = null
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${window.location.host}/api/workspace-updates`)
      socketRef.current = socket
      const connectingSocket = socket
      connectionTimer = window.setTimeout(() => {
        if (socket === connectingSocket && connectingSocket.readyState !== WebSocket.OPEN) {
          connectingSocket.close()
        }
      }, CONNECTION_TIMEOUT_MS)
      socket.addEventListener('open', () => {
        if (connectionTimer !== null) window.clearTimeout(connectionTimer)
        connectionTimer = null
        reconnectDelay = 1000
        dispatchInvalidation({ revision: null, scopes: ['all'] })
        if (viewRef.current) {
          send({ type: 'view', view: viewRef.current })
          const restored = storedPointer(workspaceId, viewRef.current)
          if (restored) pendingPointerRef.current = { view: viewRef.current, ...restored }
        }
        flushPointer()
        heartbeatTimer = window.setInterval(
          () => send({ type: 'heartbeat' }),
          HEARTBEAT_INTERVAL_MS,
        )
      })
      socket.addEventListener('message', (event) => {
        let parsed: unknown
        try {
          parsed = JSON.parse(String(event.data))
        } catch {
          return
        }
        if (isInvalidationMessage(parsed)) {
          rememberWorkspaceRevision(parsed.revision)
          dispatchInvalidation({ revision: parsed.revision, scopes: parsed.scopes })
        } else if (isPointerUpdated(parsed)) {
          setPointers((current) => [
            ...current.filter((pointer) => pointer.connectionId !== parsed.connection_id),
            {
              connectionId: parsed.connection_id,
              label: parsed.label.slice(0, 1),
              colourIndex: Math.max(0, Math.min(7, parsed.colour_index)),
              view: parsed.view,
              x: Math.max(0, Math.min(1, parsed.x)),
              y: Math.max(0, Math.min(1, parsed.y)),
            },
          ])
        } else if (isPointerRemoved(parsed)) {
          setPointers((current) =>
            current.filter((pointer) => pointer.connectionId !== parsed.connection_id),
          )
        }
      })
      socket.addEventListener('close', (event) => {
        if (connectionTimer !== null) window.clearTimeout(connectionTimer)
        connectionTimer = null
        socket = null
        socketRef.current = null
        setPointers([])
        if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
        heartbeatTimer = null
        if (!active || event.code === 4401 || event.code === 4403) return
        reconnectTimer = window.setTimeout(connect, reconnectDelay)
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS)
      })
    }

    function reconnectWhenOnline() {
      if (!active || socket !== null) return
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      reconnectTimer = null
      reconnectDelay = 1000
      connect()
    }

    function resumeWhenVisible() {
      if (document.visibilityState !== 'visible') return
      if (socket?.readyState === WebSocket.OPEN) {
        send({ type: 'heartbeat' })
        if (viewRef.current) {
          send({ type: 'view', view: viewRef.current })
          const restored = storedPointer(workspaceId, viewRef.current)
          if (restored) pendingPointerRef.current = { view: viewRef.current, ...restored }
        }
        flushPointer()
        return
      }
      reconnectWhenOnline()
    }

    window.addEventListener('online', reconnectWhenOnline)
    window.addEventListener('focus', resumeWhenVisible)
    document.addEventListener('visibilitychange', resumeWhenVisible)
    connect()
    return () => {
      active = false
      window.removeEventListener('online', reconnectWhenOnline)
      window.removeEventListener('focus', resumeWhenVisible)
      document.removeEventListener('visibilitychange', resumeWhenVisible)
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
      if (connectionTimer !== null) window.clearTimeout(connectionTimer)
      if (pointerTimerRef.current !== null) window.clearTimeout(pointerTimerRef.current)
      socket?.close()
      socketRef.current = null
    }
  }, [flushPointer, send, workspaceId])

  const context = useMemo<WorkspacePointerContextValue>(
    () => ({ pointers, setView, movePointer, hidePointer }),
    [hidePointer, movePointer, pointers, setView],
  )

  return <WorkspacePointerContext value={context}>{children}</WorkspacePointerContext>
}

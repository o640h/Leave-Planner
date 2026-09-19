import { act, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { WorkspaceUpdateConnection } from './WorkspaceUpdates'
import { useWorkspaceInvalidation } from './workspaceInvalidation'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  readonly listeners = new Map<string, Set<EventListener>>()
  closed = false

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, listener: EventListener): void {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>()
    listeners.add(listener)
    this.listeners.set(type, listeners)
  }

  emit(type: string, event: Event): void {
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }

  close(): void {
    this.closed = true
  }
}

afterEach(() => {
  FakeWebSocket.instances = []
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function PlanningObserver({ onRefresh }: { onRefresh: () => void }) {
  useWorkspaceInvalidation(['planning'], onRefresh)
  return null
}

it('refetches after reconnect and only reacts to relevant invalidations', () => {
  vi.useFakeTimers()
  vi.stubGlobal('WebSocket', FakeWebSocket)
  const onRefresh = vi.fn()
  const view = render(
    <>
      <WorkspaceUpdateConnection workspaceId={12} />
      <PlanningObserver onRefresh={onRefresh} />
    </>,
  )

  const first = FakeWebSocket.instances[0]
  expect(first.url).toBe('ws://localhost:3000/api/workspace-updates')

  act(() => first.emit('open', new Event('open')))
  expect(onRefresh).toHaveBeenCalledOnce()
  onRefresh.mockClear()

  act(() =>
    first.emit(
      'message',
      new MessageEvent('message', {
        data: JSON.stringify({
          type: 'workspace_invalidated',
          revision: 7,
          scopes: ['holidays'],
        }),
      }),
    ),
  )
  expect(onRefresh).not.toHaveBeenCalled()

  act(() =>
    first.emit(
      'message',
      new MessageEvent('message', {
        data: JSON.stringify({
          type: 'workspace_invalidated',
          revision: 8,
          scopes: ['planning'],
        }),
      }),
    ),
  )
  expect(onRefresh).toHaveBeenCalledOnce()
  onRefresh.mockClear()

  act(() => {
    first.emit('close', new CloseEvent('close', { code: 1006 }))
    vi.advanceTimersByTime(1000)
  })
  expect(FakeWebSocket.instances).toHaveLength(2)

  act(() => FakeWebSocket.instances[1].emit('open', new Event('open')))
  expect(onRefresh).toHaveBeenCalledOnce()

  view.unmount()
  expect(FakeWebSocket.instances[1].closed).toBe(true)
})

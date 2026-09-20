import { act, render, screen } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, it, vi } from 'vitest'

import { WorkspaceUpdateProvider } from './WorkspaceUpdates'
import { useWorkspaceInvalidation } from './workspaceInvalidation'
import { useWorkspacePointers } from './workspacePointers'

class FakeWebSocket {
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []

  readonly listeners = new Map<string, Set<EventListener>>()
  readonly sent: string[] = []
  readyState = 0
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
    if (type === 'open') this.readyState = FakeWebSocket.OPEN
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }

  send(message: string): void {
    this.sent.push(message)
  }

  close(): void {
    this.closed = true
    this.readyState = 3
  }
}

afterEach(() => {
  FakeWebSocket.instances = []
  window.sessionStorage.clear()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function PlanningObserver({ onRefresh }: { onRefresh: () => void }) {
  useWorkspaceInvalidation(['planning'], onRefresh)
  const { pointers, onPointerMove } = useWorkspacePointers('planning:2026-09')

  useEffect(() => {
    if (!pointers.length) return
  }, [pointers])

  return (
    <div
      data-testid="canvas"
      onPointerMove={onPointerMove}
      ref={(element) => {
        if (element) {
          element.getBoundingClientRect = () =>
            ({ left: 0, top: 0, width: 100, height: 100 }) as DOMRect
        }
      }}
    >
      {pointers.map((pointer) => `${pointer.label}:${pointer.x}:${pointer.y}`).join(',')}
    </div>
  )
}

it('reconnects, invalidates relevant data, and exchanges only normalized pointer data', () => {
  vi.useFakeTimers()
  vi.stubGlobal('WebSocket', FakeWebSocket)
  const onRefresh = vi.fn()
  const view = render(
    <WorkspaceUpdateProvider workspaceId={12}>
      <PlanningObserver onRefresh={onRefresh} />
    </WorkspaceUpdateProvider>,
  )

  const first = FakeWebSocket.instances[0]
  expect(first.url).toBe('ws://localhost:3000/api/workspace-updates')

  act(() => {
    screen
      .getByTestId('canvas')
      .dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 10, clientY: 20 }))
    vi.advanceTimersByTime(50)
  })
  expect(first.sent).toEqual([])

  act(() => first.emit('open', new Event('open')))
  expect(onRefresh).toHaveBeenCalledOnce()
  expect(first.sent.map((message) => JSON.parse(message))).toContainEqual({
    type: 'view',
    view: 'planning:2026-09',
  })
  expect(first.sent.map((message) => JSON.parse(message))).toContainEqual({
    type: 'pointer',
    view: 'planning:2026-09',
    x: 0.1,
    y: 0.2,
  })
  onRefresh.mockClear()

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

  act(() =>
    first.emit(
      'message',
      new MessageEvent('message', {
        data: JSON.stringify({
          type: 'pointer_updated',
          connection_id: 'remote-1',
          label: 'Alex',
          colour_index: 3,
          view: 'planning:2026-09',
          x: 0.35,
          y: 0.6,
        }),
      }),
    ),
  )
  expect(screen.getByTestId('canvas')).toHaveTextContent('A:0.35:0.6')

  act(() => {
    screen
      .getByTestId('canvas')
      .dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 40, clientY: 70 }))
    vi.advanceTimersByTime(50)
  })
  expect(first.sent.map((message) => JSON.parse(message))).toContainEqual({
    type: 'pointer',
    view: 'planning:2026-09',
    x: 0.4,
    y: 0.7,
  })

  act(() => {
    first.emit('close', new CloseEvent('close', { code: 1006 }))
    vi.advanceTimersByTime(1000)
  })
  expect(FakeWebSocket.instances).toHaveLength(2)

  act(() => FakeWebSocket.instances[1].emit('open', new Event('open')))
  expect(FakeWebSocket.instances[1].sent.map((message) => JSON.parse(message))).toContainEqual({
    type: 'pointer',
    view: 'planning:2026-09',
    x: 0.4,
    y: 0.7,
  })

  act(() => {
    FakeWebSocket.instances[1].emit('close', new CloseEvent('close', { code: 1006 }))
    vi.advanceTimersByTime(2000)
    FakeWebSocket.instances[2].emit('close', new CloseEvent('close', { code: 1006 }))
    vi.advanceTimersByTime(4000)
    FakeWebSocket.instances[3].emit('close', new CloseEvent('close', { code: 1006 }))
    vi.advanceTimersByTime(5000)
  })
  expect(FakeWebSocket.instances).toHaveLength(5)

  view.unmount()
  expect(FakeWebSocket.instances[4].closed).toBe(true)
})

it('publishes the last pointer position immediately after a refresh', () => {
  vi.stubGlobal('WebSocket', FakeWebSocket)

  const firstView = render(
    <WorkspaceUpdateProvider workspaceId={12}>
      <PlanningObserver onRefresh={vi.fn()} />
    </WorkspaceUpdateProvider>,
  )
  const firstSocket = FakeWebSocket.instances[0]
  act(() => firstSocket.emit('open', new Event('open')))
  act(() => {
    screen
      .getByTestId('canvas')
      .dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 25, clientY: 60 }))
    window.dispatchEvent(new Event('blur'))
  })
  firstView.unmount()

  render(
    <WorkspaceUpdateProvider workspaceId={12}>
      <PlanningObserver onRefresh={vi.fn()} />
    </WorkspaceUpdateProvider>,
  )
  const refreshedSocket = FakeWebSocket.instances[1]
  act(() => refreshedSocket.emit('open', new Event('open')))

  expect(refreshedSocket.sent.map((message) => JSON.parse(message))).toContainEqual({
    type: 'pointer',
    view: 'planning:2026-09',
    x: 0.25,
    y: 0.6,
  })
})

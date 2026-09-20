import { createContext, useContext, useEffect, type PointerEvent as ReactPointerEvent } from 'react'

export type RemotePointer = {
  connectionId: string
  label: string
  colourIndex: number
  view: string
  x: number
  y: number
}

export type WorkspacePointerContextValue = {
  pointers: RemotePointer[]
  setView: (view: string | null) => void
  movePointer: (view: string, x: number, y: number) => void
  hidePointer: () => void
}

export const WorkspacePointerContext = createContext<WorkspacePointerContextValue | null>(null)

export function useWorkspacePointers(view: string) {
  const context = useContext(WorkspacePointerContext)
  const setView = context?.setView

  useEffect(() => {
    setView?.(view)
    return () => setView?.(null)
  }, [setView, view])

  function onPointerMove(event: ReactPointerEvent<HTMLElement>) {
    if (!context || event.pointerType === 'touch') return
    const bounds = event.currentTarget.getBoundingClientRect()
    if (bounds.width <= 0 || bounds.height <= 0) return
    const x = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width))
    const y = Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height))
    context.movePointer(view, x, y)
  }

  return {
    pointers: context?.pointers.filter((pointer) => pointer.view === view) ?? [],
    onPointerMove,
    onPointerLeave: () => context?.hidePointer(),
  }
}

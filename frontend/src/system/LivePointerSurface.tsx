import type { ReactNode } from 'react'

import { LivePointerLayer } from './LivePointerLayer'
import { useWorkspacePointers } from './workspacePointers'

export function LivePointerSurface({ view, children }: { view: string; children: ReactNode }) {
  const { pointers, onPointerMove, onPointerLeave } = useWorkspacePointers(view)

  return (
    <div
      className="live-pointer-surface"
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
    >
      {children}
      <LivePointerLayer pointers={pointers} />
    </div>
  )
}

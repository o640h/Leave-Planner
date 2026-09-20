import type { CSSProperties } from 'react'

import type { RemotePointer } from './workspacePointers'

export function LivePointerLayer({ pointers }: { pointers: RemotePointer[] }) {
  return (
    <div className="live-pointer-layer" aria-hidden="true">
      {pointers.map((pointer) => (
        <span
          className="live-pointer"
          key={pointer.connectionId}
          style={
            {
              '--live-pointer-x': `${pointer.x * 100}%`,
              '--live-pointer-y': `${pointer.y * 100}%`,
              '--live-pointer-colour': `var(--live-pointer-${pointer.colourIndex})`,
            } as CSSProperties
          }
        >
          <svg viewBox="0 0 20 24" focusable="false">
            <path d="M2 1.5v17.2l4.6-4 3.2 7.1 3-1.4-3.2-6.9h6.2L2 1.5Z" />
          </svg>
          <span>{pointer.label}</span>
        </span>
      ))}
    </div>
  )
}

import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

type Size = { width: number; height: number }

export function WorkspaceFrame({ children }: { children: ReactNode }) {
  const [size, setSize] = useState<Size>({ width: 1440, height: 900 })
  const [expanded, setExpanded] = useState(false)
  const frame = useRef<HTMLDivElement>(null)
  const drag = useRef<(Size & { x: number; y: number }) | null>(null)

  useLayoutEffect(() => {
    const element = frame.current
    if (!element) return
    if (expanded) {
      element.style.removeProperty('width')
      element.style.removeProperty('height')
    } else {
      element.style.width = `${Math.min(window.innerWidth, size.width)}px`
      element.style.height = `${Math.min(window.innerHeight, size.height)}px`
    }
  }, [expanded, size])

  function resize(width: number, height: number) {
    setSize({
      width: Math.max(720, Math.min(window.innerWidth, width)),
      height: Math.max(480, Math.min(window.innerHeight, height)),
    })
  }

  return (
    <div
      ref={frame}
      className={`application-frame workspace-frame${expanded ? ' workspace-frame--expanded' : ''}`}
    >
      {children}
      <div className="workspace-sizing" aria-label="Workspace size">
        <button type="button" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Restore Size' : 'Fill Window'}
        </button>
        <button
          type="button"
          className="workspace-resize"
          aria-label="Resize Workspace"
          title="Drag to resize, or use arrow keys when focused"
          disabled={expanded}
          onPointerDown={(event) => {
            if (event.button !== 0) return
            const bounds = frame.current!.getBoundingClientRect()
            drag.current = {
              width: bounds.width,
              height: bounds.height,
              x: event.clientX,
              y: event.clientY,
            }
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
          onPointerMove={(event) => {
            if (!drag.current) return
            const start = drag.current
            // The frame is centred, so both edges move by half of the size change.
            resize(
              start.width + 2 * (event.clientX - start.x),
              start.height + 2 * (event.clientY - start.y),
            )
          }}
          onPointerUp={() => {
            drag.current = null
          }}
          onPointerCancel={() => {
            drag.current = null
          }}
          onLostPointerCapture={() => {
            drag.current = null
          }}
          onKeyDown={(event) => {
            const steps: Record<string, [number, number]> = {
              ArrowLeft: [-40, 0],
              ArrowRight: [40, 0],
              ArrowUp: [0, -40],
              ArrowDown: [0, 40],
            }
            const step = steps[event.key]
            if (!step) return
            event.preventDefault()
            const bounds = frame.current!.getBoundingClientRect()
            resize(bounds.width + step[0], bounds.height + step[1])
          }}
        >
          <svg aria-hidden="true" viewBox="0 0 16 16">
            <path d="M4 12 12 4M8 12l4-4" />
          </svg>
        </button>
      </div>
    </div>
  )
}

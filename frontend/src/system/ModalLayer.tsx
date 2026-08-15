import { useEffect, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'

type ModalLayerProps = {
  children: ReactNode
  onClose: () => void
}

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export function ModalLayer({ children, onClose }: ModalLayerProps) {
  const layerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = layerRef.current?.querySelector<HTMLElement>('[role="dialog"]')
    if (!dialog) return

    dialog.focus()
    return () => previousFocus?.focus()
  }, [])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab') return

    const focusable = Array.from(
      layerRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? [],
    )
    if (focusable.length === 0) {
      event.preventDefault()
      layerRef.current?.querySelector<HTMLElement>('[role="dialog"]')?.focus()
      return
    }

    const first = focusable[0]
    const last = focusable.at(-1)
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const applicationContent = document.querySelector('.application-content')
  const layer = (
    <div className="modal-layer" ref={layerRef} onKeyDown={handleKeyDown}>
      {children}
    </div>
  )
  return applicationContent ? createPortal(layer, applicationContent) : layer
}

import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

type ModalLayerProps = {
  children: ReactNode
}

export function ModalLayer({ children }: ModalLayerProps) {
  const applicationContent = document.querySelector('.application-content')
  return applicationContent ? createPortal(children, applicationContent) : children
}

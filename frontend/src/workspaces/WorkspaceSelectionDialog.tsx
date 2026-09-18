import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import { ModalLayer } from '../system/ModalLayer'
import { selectWorkspace } from './api'

type WorkspaceSelectionDialogProps = {
  context: WorkspaceContext
  closeRequested?: boolean
  onClose: () => void
  onSelected: (context: WorkspaceContext) => void
  onCreateWorkspace?: () => void
}

const roleLabels = { owner: 'Owner', admin: 'Admin', member: 'Member' } as const

export function WorkspaceSelectionDialog({
  context,
  closeRequested = false,
  onClose,
  onSelected,
  onCreateWorkspace,
}: WorkspaceSelectionDialogProps) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [closing, setClosing] = useState(false)
  const [createAfterClose, setCreateAfterClose] = useState(false)
  const isClosing = closing || (closeRequested && busyId === null)

  useEffect(() => {
    if (!isClosing) return
    const timeout = window.setTimeout(() => {
      onClose()
      if (createAfterClose) onCreateWorkspace?.()
    }, 220)
    return () => window.clearTimeout(timeout)
  }, [createAfterClose, isClosing, onClose, onCreateWorkspace])

  function requestClose() {
    if (busyId === null) {
      setCreateAfterClose(false)
      setClosing(true)
    }
  }

  function requestCreate() {
    if (busyId === null && onCreateWorkspace) {
      setCreateAfterClose(true)
      setClosing(true)
    }
  }

  async function choose(workspaceId: number) {
    if (busyId !== null) return
    if (workspaceId === context.active_workspace_id) {
      requestClose()
      return
    }

    setBusyId(workspaceId)
    setError(null)
    try {
      onSelected(await selectWorkspace(workspaceId))
      setClosing(true)
    } catch (selectionError) {
      setError(operatorErrorMessage(selectionError))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <ModalLayer onClose={requestClose}>
      <div
        className={`modal-backdrop workspace-selection-backdrop${
          isClosing ? ' workspace-selection-backdrop--closing' : ''
        }`}
      >
        <section
          className={`record-modal workspace-selection-dialog${
            isClosing ? ' workspace-selection-dialog--closing' : ''
          }`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="workspace-selection-dialog-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Workspace Selection"
            disabled={busyId !== null || isClosing}
            onClick={requestClose}
          >
            x
          </button>
          <header>
            <span className="section-label">Current Context</span>
            <h2 id="workspace-selection-dialog-title">Choose Workspace</h2>
          </header>
          <div className="workspace-selection-list">
            {context.memberships.map((membership) => {
              const selected = membership.workspace_id === context.active_workspace_id
              return (
                <button
                  className={`workspace-selection-option${
                    selected ? ' workspace-selection-option--active' : ''
                  }`}
                  type="button"
                  key={membership.workspace_id}
                  disabled={busyId !== null || isClosing}
                  aria-current={selected ? 'page' : undefined}
                  onClick={() => void choose(membership.workspace_id)}
                >
                  <span>
                    <strong>{membership.workspace_name}</strong>
                    <small>{roleLabels[membership.role]}</small>
                  </span>
                  <span>
                    {busyId === membership.workspace_id ? 'Opening...' : selected ? 'Open' : ''}
                  </span>
                </button>
              )
            })}
          </div>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <footer className="form-actions">
            {onCreateWorkspace ? (
              <button
                className="button button--overview-action"
                type="button"
                disabled={busyId !== null || isClosing}
                onClick={requestCreate}
              >
                Create Workspace
              </button>
            ) : null}
            <button
              className="button button--quiet"
              type="button"
              disabled={busyId !== null || isClosing}
              onClick={requestClose}
            >
              Cancel
            </button>
          </footer>
        </section>
      </div>
    </ModalLayer>
  )
}

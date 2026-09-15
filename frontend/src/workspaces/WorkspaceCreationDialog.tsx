import { FormEvent, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { WorkspaceContext } from '../authentication/types'
import { ModalLayer } from '../system/ModalLayer'
import { createWorkspace } from './api'

type WorkspaceCreationDialogProps = {
  onCancel: () => void
  onCreated: (context: WorkspaceContext) => void
}

export function WorkspaceCreationDialog({ onCancel, onCreated }: WorkspaceCreationDialogProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const workspaceName = name.trim()
    if (!workspaceName) {
      setError('Enter a workspace name.')
      return
    }

    setError(null)
    setSaving(true)
    try {
      onCreated(await createWorkspace(workspaceName))
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalLayer onClose={() => !saving && onCancel()}>
      <div className="modal-backdrop">
        <section
          className="record-modal workspace-creation-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="workspace-creation-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Create Workspace"
            disabled={saving}
            onClick={onCancel}
          >
            x
          </button>
          <form noValidate onSubmit={submit}>
            <div className="form-introduction">
              <span className="section-label">New Workspace</span>
              <h3 id="workspace-creation-title">Create Workspace</h3>
              <p>This creates an empty workspace with you as its Owner.</p>
            </div>
            <div className="form-fields">
              <div className="field">
                <label htmlFor="workspace-name">Workspace Name</label>
                <input
                  id="workspace-name"
                  name="name"
                  autoComplete="off"
                  autoFocus
                  maxLength={160}
                  value={name}
                  aria-required="true"
                  aria-invalid={error ? 'true' : undefined}
                  aria-describedby={error ? 'workspace-name-error' : undefined}
                  disabled={saving}
                  onChange={(event) => {
                    setError(null)
                    setName(event.target.value)
                  }}
                />
                {error ? (
                  <small id="workspace-name-error" className="field-error" role="alert">
                    {error}
                  </small>
                ) : null}
              </div>
            </div>
            <div className="form-actions">
              <button
                className="button button--quiet"
                type="button"
                disabled={saving}
                onClick={onCancel}
              >
                Cancel
              </button>
              <button className="button button--primary" type="submit" disabled={saving}>
                {saving ? 'Creating...' : 'Create Workspace'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </ModalLayer>
  )
}

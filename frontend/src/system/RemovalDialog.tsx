import { useState } from 'react'

import { ModalLayer } from './ModalLayer'
import type { RemovalImpact } from './removal'

type Props = {
  title: string
  impact: RemovalImpact
  busy: boolean
  error: string | null
  onConfirm: (confirmation: string) => void
  onCancel: () => void
}

export function RemovalDialog({ title, impact, busy, error, onConfirm, onCancel }: Props) {
  const [confirmation, setConfirmation] = useState('')
  const matches = confirmation.trim() === impact.confirmation_text

  return (
    <ModalLayer onClose={onCancel}>
      <div className="modal-backdrop">
        <section
          className="record-modal removal-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="removal-title"
          tabIndex={-1}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close Confirmation"
            disabled={busy}
            onClick={onCancel}
          >
            ×
          </button>

          <header>
            <h2 id="removal-title">{title}</h2>
            <p>{impact.resource_name}</p>
          </header>

          {error ? (
            <p className="form-notice form-notice--error" role="alert">
              {error}
            </p>
          ) : null}

          {impact.blocking_reason ? (
            <p className="form-notice form-notice--error">{impact.blocking_reason}</p>
          ) : null}

          <ul>
            {impact.consequences.map((consequence) => (
              <li key={consequence}>{consequence}</li>
            ))}
          </ul>

          <label>
            <span>
              Type <strong>{impact.confirmation_text}</strong> to confirm
            </span>
            <input
              autoFocus
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </label>

          <footer className="form-actions">
            <button
              className="button button--quiet"
              type="button"
              disabled={busy}
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="button button--danger"
              type="button"
              disabled={busy || !matches || !impact.can_proceed}
              onClick={() => onConfirm(confirmation)}
            >
              {busy ? 'Working…' : impact.action === 'archive' ? 'Archive' : 'Delete'}
            </button>
          </footer>
        </section>
      </div>
    </ModalLayer>
  )
}

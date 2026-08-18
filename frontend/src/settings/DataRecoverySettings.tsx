import { useEffect, useState } from 'react'

import { apiRequest, operatorErrorMessage } from '../api/client'
import { ModalLayer } from '../system/ModalLayer'

type BackupKind = 'manual' | 'automatic' | 'pre-migration' | 'pre-restore'

type Backup = {
  name: string
  kind: BackupKind
  created_at: string
  size_bytes: number
}

type RecoveryStatus = {
  data_directory: string
  backup_directory: string
  backups: Backup[]
}

type RecoveryResult = {
  message: string
}

const backupKindLabels: Record<BackupKind, string> = {
  manual: 'Manual',
  automatic: 'Automatic',
  'pre-migration': 'Before Update',
  'pre-restore': 'Before Restore',
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DataRecoverySettings() {
  const [status, setStatus] = useState<RecoveryStatus | null>(null)
  const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null)
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function refreshStatus() {
    const nextStatus = await apiRequest<RecoveryStatus>('/api/settings/recovery')
    setStatus(nextStatus)
  }

  useEffect(() => {
    let active = true

    apiRequest<RecoveryStatus>('/api/settings/recovery')
      .then((result) => {
        if (active) setStatus(result)
      })
      .catch((requestError: unknown) => {
        if (active) setError(operatorErrorMessage(requestError))
      })

    return () => {
      active = false
    }
  }, [])

  async function createBackup() {
    setBusy(true)
    setError(null)
    setNotice(null)

    try {
      const result = await apiRequest<RecoveryResult>('/api/settings/recovery/backups', {
        method: 'POST',
      })
      await refreshStatus()
      setNotice(result.message)
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setBusy(false)
    }
  }

  function closeRestore() {
    if (busy) return

    setSelectedBackup(null)
    setConfirmation('')
    setError(null)
  }

  async function restoreBackup() {
    if (!selectedBackup || confirmation !== 'RESTORE') return

    setBusy(true)
    setError(null)

    try {
      await apiRequest<RecoveryResult>('/api/settings/recovery/restore', {
        method: 'POST',
        body: JSON.stringify({
          backup_name: selectedBackup.name,
          confirmation,
        }),
      })

      window.location.reload()
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
      setBusy(false)
    }
  }

  return (
    <section className="settings-section" aria-labelledby="recovery-title">
      <header className="settings-content-heading">
        <span className="section-label">Local Data</span>
        <h2 id="recovery-title">Data & Recovery</h2>
      </header>

      {notice ? (
        <p className="form-notice form-notice--success" role="status">
          {notice}
        </p>
      ) : null}

      {error && !selectedBackup ? (
        <p className="form-notice form-notice--error" role="alert">
          {error}
        </p>
      ) : null}

      <section className="settings-panel recovery-panel">
        <header>
          <div>
            <h3>Backups</h3>
            <p>Verified copies of the local Leave Planner database.</p>
          </div>

          <button
            className="button button--overview-action"
            type="button"
            disabled={busy || !status}
            onClick={createBackup}
          >
            {busy ? 'Creating...' : 'Create Backup'}
          </button>
        </header>

        {status ? (
          <dl className="recovery-locations">
            <div>
              <dt>Application Data</dt>
              <dd title={status.data_directory}>{status.data_directory}</dd>
            </div>
            <div>
              <dt>Backup Folder</dt>
              <dd title={status.backup_directory}>{status.backup_directory}</dd>
            </div>
          </dl>
        ) : null}

        <div className="backup-list">
          {status?.backups.length ? (
            status.backups.map((backup) => (
              <article className="backup-row" key={backup.name}>
                <div>
                  <strong>{backupKindLabels[backup.kind]} Backup</strong>
                  <span>{formatDate(backup.created_at)}</span>
                </div>

                <span className="backup-size">{formatSize(backup.size_bytes)}</span>

                <button
                  className="button button--quiet"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setSelectedBackup(backup)
                    setConfirmation('')
                    setError(null)
                    setNotice(null)
                  }}
                >
                  Restore
                </button>
              </article>
            ))
          ) : (
            <p className="recovery-empty">No backups have been created yet.</p>
          )}
        </div>
      </section>

      {selectedBackup ? (
        <ModalLayer onClose={closeRestore}>
          <div className="modal-backdrop">
            <section
              className="record-modal recovery-restore-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="restore-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label="Close Restore Backup"
                disabled={busy}
                onClick={closeRestore}
              >
                x
              </button>

              <header>
                <span className="section-label">Data Recovery</span>
                <h2 id="restore-title">Restore Backup</h2>
                <p>{formatDate(selectedBackup.created_at)}</p>
              </header>

              <p>The current database will be backed up, then replaced.</p>

              {error ? (
                <p className="form-notice form-notice--error" role="alert">
                  {error}
                </p>
              ) : null}

              <label>
                <span>
                  Type <strong>RESTORE</strong> to confirm
                </span>
                <input
                  autoFocus
                  autoComplete="off"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
              </label>

              <footer className="form-actions">
                <button
                  className="button button--quiet"
                  type="button"
                  disabled={busy}
                  onClick={closeRestore}
                >
                  Cancel
                </button>
                <button
                  className="button button--danger"
                  type="button"
                  disabled={busy || confirmation !== 'RESTORE'}
                  onClick={restoreBackup}
                >
                  {busy ? 'Restoring...' : 'Restore Backup'}
                </button>
              </footer>
            </section>
          </div>
        </ModalLayer>
      ) : null}
    </section>
  )
}

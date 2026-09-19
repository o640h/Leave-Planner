import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import {
  archiveConsultant,
  consultantArchiveImpact,
  createConsultant,
  listConsultants,
  updateConsultant,
} from './api'
import { ConsultantForm } from './ConsultantForm'
import { emptyConsultantInput, type Consultant, type ConsultantInput } from './types'
import './consultants.css'

import { LeaveYearPanel } from '../leaveYears/LeaveYearPanel'
import { AppIcon } from '../system/AppIcon'
import { ModalLayer } from '../system/ModalLayer'
import { RemovalDialog } from '../system/RemovalDialog'
import { useWorkspaceInvalidation } from '../system/workspaceInvalidation'
import type { RemovalImpact } from '../system/removal'

type EditorTarget = number | 'new' | null

function sortConsultants(consultants: Consultant[]): Consultant[] {
  return [...consultants].sort((first, second) => {
    const nameOrder = first.name.localeCompare(second.name)

    return nameOrder === 0 ? first.id - second.id : nameOrder
  })
}

function consultantInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  const firstInitial = parts[0]?.[0] ?? ''
  const lastInitial = parts.length > 1 ? (parts.at(-1)?.[0] ?? '') : ''

  return `${firstInitial}${lastInitial}`.toLocaleUpperCase()
}

export function ConsultantDirectory() {
  const [consultants, setConsultants] = useState<Consultant[]>([])
  const [editorTarget, setEditorTarget] = useState<EditorTarget>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [identityEditorOpen, setIdentityEditorOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [archiveImpact, setArchiveImpact] = useState<RemovalImpact | null>(null)
  const [removing, setRemoving] = useState(false)

  useWorkspaceInvalidation(['consultants'], () => {
    setLoadAttempt((attempt) => attempt + 1)
  })

  useEffect(() => {
    listConsultants()
      .then((records) => {
        const orderedRecords = sortConsultants(records)
        setConsultants(orderedRecords)
        setEditorTarget((current) =>
          typeof current === 'number' && orderedRecords.some((record) => record.id === current)
            ? current
            : (orderedRecords[0]?.id ?? null),
        )
      })
      .catch((error: unknown) => setLoadError(operatorErrorMessage(error)))
      .finally(() => setLoading(false))
  }, [loadAttempt])

  function retryLoading() {
    setLoading(true)
    setLoadError(null)
    setLoadAttempt((attempt) => attempt + 1)
  }

  const selectedConsultant =
    typeof editorTarget === 'number'
      ? (consultants.find((consultant) => consultant.id === editorTarget) ?? null)
      : null

  const formValue: ConsultantInput = selectedConsultant
    ? {
        name: selectedConsultant.name,
        post_title: selectedConsultant.post_title,
      }
    : emptyConsultantInput()

  async function saveConsultant(details: ConsultantInput) {
    if (editorTarget === null) return

    setSaving(true)
    setSaveError(null)
    setNotice(null)

    try {
      const saved =
        editorTarget === 'new'
          ? await createConsultant(details)
          : await updateConsultant(editorTarget, details)

      setConsultants((current) => {
        const next =
          editorTarget === 'new'
            ? [...current, saved]
            : current.map((consultant) => (consultant.id === saved.id ? saved : consultant))

        return sortConsultants(next)
      })

      setEditorTarget(saved.id)
      setIdentityEditorOpen(false)
      setNotice(
        editorTarget === 'new'
          ? `${saved.name} was added to the directory.`
          : `${saved.name} was updated.`,
      )
    } catch (error) {
      setSaveError(operatorErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  function selectConsultant(consultantId: number) {
    setEditorTarget(consultantId)
    setIdentityEditorOpen(false)
    setSaveError(null)
    setNotice(null)
  }

  function beginCreate() {
    setEditorTarget('new')
    setIdentityEditorOpen(false)
    setSaveError(null)
    setNotice(null)
  }

  function cancelEditing() {
    setSaveError(null)
    setNotice(null)

    if (editorTarget === 'new') setEditorTarget(consultants[0]?.id ?? null)
    setIdentityEditorOpen(false)
  }

  async function beginArchive() {
    if (!selectedConsultant) return
    setSaveError(null)
    try {
      setArchiveImpact(await consultantArchiveImpact(selectedConsultant.id))
    } catch (error) {
      setSaveError(operatorErrorMessage(error))
    }
  }

  async function confirmArchive(confirmation: string) {
    if (!selectedConsultant) return
    setRemoving(true)
    setSaveError(null)
    try {
      const result = await archiveConsultant(selectedConsultant.id, confirmation)
      const remaining = consultants.filter((consultant) => consultant.id !== selectedConsultant.id)
      setConsultants(remaining)
      setEditorTarget(remaining[0]?.id ?? null)
      setArchiveImpact(null)
      setIdentityEditorOpen(false)
      setNotice(result.message)
    } catch (error) {
      setSaveError(operatorErrorMessage(error))
    } finally {
      setRemoving(false)
    }
  }

  const normalizedQuery = searchQuery.trim().toLocaleLowerCase()
  const visibleConsultants = normalizedQuery
    ? consultants.filter((consultant) =>
        `${consultant.name} ${consultant.post_title ?? ''}`
          .toLocaleLowerCase()
          .includes(normalizedQuery),
      )
    : consultants

  return (
    <section className="directory" aria-labelledby="directory-title">
      <div className="directory-workspace">
        <section className="directory-list-panel" aria-labelledby="consultant-list-title">
          <div className="panel-heading">
            <div>
              <h2 id="directory-title">Consultants</h2>
              <span id="consultant-list-title">
                {consultants.length} {consultants.length === 1 ? 'record' : 'records'}
              </span>
            </div>
            <button
              className="icon-text-button panel-add-button"
              type="button"
              title="Add Consultant"
              aria-label="Add Consultant"
              onClick={beginCreate}
            >
              <AppIcon name="plus" />
            </button>
          </div>

          <div className="consultant-search">
            <AppIcon name="search" />
            <label className="visually-hidden" htmlFor="consultant-search">
              Search
            </label>
            <input
              id="consultant-search"
              type="search"
              placeholder="Search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <div className="directory-list-body">
            {loading ? (
              <p className="panel-message" aria-live="polite">
                Loading consultant records...
              </p>
            ) : loadError ? (
              <div className="panel-message panel-message--error" role="alert">
                <p>{loadError}</p>
                <button
                  className="button button--overview-action panel-message-action"
                  type="button"
                  onClick={retryLoading}
                >
                  Try Again
                </button>
              </div>
            ) : consultants.length === 0 ? (
              <div className="panel-message">
                <p>No consultants have been added.</p>
                <span>Use Add Consultant to create the first record.</span>
              </div>
            ) : visibleConsultants.length === 0 ? (
              <div className="panel-message">
                <p>No matching consultants.</p>
                <span>Try a different name or post title.</span>
              </div>
            ) : (
              <ol className="consultant-list">
                {visibleConsultants.map((consultant) => {
                  const selected = consultant.id === editorTarget
                  const index = consultants.indexOf(consultant)

                  return (
                    <li key={consultant.id}>
                      <button
                        className={`consultant-row${selected ? ' consultant-row--selected' : ''}`}
                        type="button"
                        aria-current={selected ? 'true' : undefined}
                        onClick={() => selectConsultant(consultant.id)}
                      >
                        <span className="consultant-index">
                          {(index + 1).toString().padStart(2, '0')}
                        </span>
                        <span className="consultant-summary">
                          <strong>{consultant.name}</strong>
                          <small>{consultant.post_title ?? 'Post Title Not Set'}</small>
                        </span>
                        <span className="consultant-action">{selected ? 'Selected' : 'Open'}</span>
                      </button>
                    </li>
                  )
                })}
              </ol>
            )}
          </div>
        </section>

        <section className="directory-editor-panel" aria-label="Consultant Editor">
          {notice ? (
            <p className="form-notice form-notice--success" role="status">
              {notice}
            </p>
          ) : null}

          {saveError && editorTarget !== 'new' ? (
            <p className="form-notice form-notice--error" role="alert">
              {saveError}
            </p>
          ) : null}

          {selectedConsultant ? (
            <div className="consultant-workspace">
              <header className="consultant-workspace-header">
                <div className="consultant-identity">
                  <span className="consultant-monogram" aria-hidden="true">
                    {consultantInitials(selectedConsultant.name)}
                  </span>
                  <div>
                    <h3>{selectedConsultant.name}</h3>
                    <p>{selectedConsultant.post_title ?? 'Post Title Not Set'}</p>
                  </div>
                </div>
                <div className="consultant-header-actions">
                  <button
                    className="button button--quiet overview-delete-button"
                    type="button"
                    onClick={beginArchive}
                  >
                    Archive
                  </button>
                  <button
                    className="button button--overview-action button--with-icon"
                    type="button"
                    onClick={() => setIdentityEditorOpen(true)}
                  >
                    <AppIcon name="edit" />
                    <span>Edit Consultant</span>
                  </button>
                </div>
              </header>

              <LeaveYearPanel
                key={`${selectedConsultant.id}:${loadAttempt}`}
                consultantId={selectedConsultant.id}
              />
            </div>
          ) : (
            <div className="workspace-empty">
              <span className="section-label">Consultant Workspace</span>
              <h3>No Consultant Selected</h3>
              <p>Select a consultant from the list or create a new record.</p>
              <button
                className="button button--overview-action workspace-empty-action"
                type="button"
                onClick={beginCreate}
              >
                Create First Consultant
              </button>
            </div>
          )}
        </section>
      </div>

      {editorTarget === 'new' || (selectedConsultant && identityEditorOpen) ? (
        <ModalLayer onClose={cancelEditing}>
          <div className="modal-backdrop">
            <section
              className="record-modal record-modal--lined"
              role="dialog"
              aria-modal="true"
              aria-labelledby="consultant-form-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label={
                  editorTarget === 'new' ? 'Close Add Consultant' : 'Close Edit Consultant'
                }
                disabled={saving}
                onClick={cancelEditing}
              >
                x
              </button>

              {saveError ? (
                <p className="form-notice form-notice--error" role="alert">
                  {saveError}
                </p>
              ) : null}

              <ConsultantForm
                key={editorTarget === 'new' ? 'new' : selectedConsultant?.id}
                initialValue={editorTarget === 'new' ? emptyConsultantInput() : formValue}
                mode={editorTarget === 'new' ? 'create' : 'edit'}
                busy={saving}
                onSubmit={saveConsultant}
                onCancel={cancelEditing}
              />
            </section>
          </div>
        </ModalLayer>
      ) : null}

      {archiveImpact ? (
        <RemovalDialog
          title="Archive Consultant"
          impact={archiveImpact}
          busy={removing}
          error={saveError}
          onConfirm={confirmArchive}
          onCancel={() => {
            if (!removing) {
              setArchiveImpact(null)
              setSaveError(null)
            }
          }}
        />
      ) : null}
    </section>
  )
}

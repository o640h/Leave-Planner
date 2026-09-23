import { useCallback, useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { CarryForwardControl } from '../carryForward/CarryForwardControl'
import { getConsultantYearSummary } from '../consultantSummary/api'
import {
  ConsultantYearSummarySections,
  LeaveBalanceSummary,
} from '../consultantSummary/ConsultantYearSummarySections'
import type { ConsultantYearSummary } from '../consultantSummary/types'
import { JobPlanPanel } from '../jobPlans/JobPlanPanel'
import { AppIcon } from '../system/AppIcon'
import { ModalLayer } from '../system/ModalLayer'
import {
  createLeaveYear,
  leaveYearRemovalImpact,
  listLeaveYears,
  removeLeaveYear,
  updateLeaveYear,
} from './api'
import { LeaveYearForm } from './LeaveYearForm'
import { emptyLeaveYearInput, type LeaveYear, type LeaveYearInput } from './types'
import { EntitlementPanel } from '../annualEntitlement/EntitlementPanel'
import { RemovalDialog } from '../system/RemovalDialog'
import type { RemovalImpact } from '../system/removal'
import './leaveYears.css'

type EditorTarget = LeaveYear | 'new' | null

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function sortLeaveYears(years: LeaveYear[]): LeaveYear[] {
  return [...years].sort((first, second) => second.start_date.localeCompare(first.start_date))
}

function editableValue(leaveYear: LeaveYear): LeaveYearInput {
  return {
    start_date: leaveYear.start_date,
    end_date: leaveYear.end_date,
    employment_start: leaveYear.employment_start,
    employment_end: leaveYear.employment_end,
  }
}

type LeaveYearPanelProps = {
  consultantId: number
}

export function LeaveYearPanel({ consultantId }: LeaveYearPanelProps) {
  const [leaveYears, setLeaveYears] = useState<LeaveYear[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [editorTarget, setEditorTarget] = useState<EditorTarget>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [calculationRevision, setCalculationRevision] = useState(0)
  const [entitlementReloadRevision, setEntitlementReloadRevision] = useState(0)
  const [removalImpact, setRemovalImpact] = useState<RemovalImpact | null>(null)
  const [removing, setRemoving] = useState(false)
  const [removalError, setRemovalError] = useState<string | null>(null)
  const [summary, setSummary] = useState<ConsultantYearSummary | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [summaryRevision, setSummaryRevision] = useState(0)

  useEffect(() => {
    listLeaveYears(consultantId)
      .then((records) => {
        const ordered = sortLeaveYears(records)
        setLeaveYears(ordered)
        setSelectedId(ordered[0]?.id ?? null)
      })
      .catch((requestError: unknown) => setError(operatorErrorMessage(requestError)))
      .finally(() => setLoading(false))
  }, [consultantId, loadAttempt])

  function retryLoading() {
    setLoading(true)
    setError(null)
    setLoadAttempt((attempt) => attempt + 1)
  }

  const selectedLeaveYear = leaveYears.find((leaveYear) => leaveYear.id === selectedId) ?? null

  useEffect(() => {
    if (selectedId === null) return
    let active = true
    getConsultantYearSummary(consultantId, selectedId)
      .then((result) => {
        if (active) {
          setSummary(result)
          setSummaryError(null)
        }
      })
      .catch((requestError: unknown) => {
        if (active) setSummaryError(operatorErrorMessage(requestError))
      })
    return () => {
      active = false
    }
  }, [consultantId, selectedId, summaryRevision])

  const refreshSummary = useCallback(() => {
    setSummaryRevision((revision) => revision + 1)
  }, [])
  const selectedSummary = summary?.leave_year.id === selectedId ? summary : null

  async function saveLeaveYear(details: LeaveYearInput) {
    if (editorTarget === null) return

    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const saved =
        editorTarget === 'new'
          ? await createLeaveYear(consultantId, details)
          : await updateLeaveYear(consultantId, editorTarget.id, details)

      setLeaveYears((current) => {
        const next =
          editorTarget === 'new'
            ? [...current, saved]
            : current.map((leaveYear) => (leaveYear.id === saved.id ? saved : leaveYear))

        return sortLeaveYears(next)
      })

      setSelectedId(saved.id)
      setEditorTarget(null)
      setNotice(
        editorTarget === 'new' ? 'The leave year was created.' : 'The leave year was updated.',
      )
      setCalculationRevision((revision) => revision + 1)
      refreshSummary()
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    } finally {
      setSaving(false)
    }
  }

  function closeEditor() {
    if (!saving) {
      setEditorTarget(null)
      setError(null)
    }
  }

  async function beginRemoval() {
    if (!selectedLeaveYear) return
    setRemovalError(null)
    try {
      setRemovalImpact(await leaveYearRemovalImpact(consultantId, selectedLeaveYear.id))
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
    }
  }

  async function confirmRemoval(confirmation: string) {
    if (!selectedLeaveYear) return
    setRemoving(true)
    setRemovalError(null)
    try {
      const result = await removeLeaveYear(consultantId, selectedLeaveYear.id, confirmation)
      const remaining = leaveYears.filter((leaveYear) => leaveYear.id !== selectedLeaveYear.id)
      setLeaveYears(remaining)
      setSelectedId(remaining[0]?.id ?? null)
      setRemovalImpact(null)
      setNotice(result.message)
    } catch (requestError) {
      setRemovalError(operatorErrorMessage(requestError))
    } finally {
      setRemoving(false)
    }
  }

  return (
    <section className="leave-year-panel" aria-label="Overview">
      {notice ? (
        <p className="form-notice form-notice--success" role="status">
          {notice}
        </p>
      ) : null}

      {loading ? (
        <p className="leave-year-message">Loading leave years...</p>
      ) : error && editorTarget === null ? (
        <div className="leave-year-message form-notice--error" role="alert">
          <p>{error}</p>
          <button className="text-button" type="button" onClick={retryLoading}>
            Try Again
          </button>
        </div>
      ) : (
        <>
          {leaveYears.length === 0 ? (
            <div className="dashboard-empty">
              <div>
                <h4>No Leave Year Configured</h4>
                <p>Add the consultant's annual leave period before configuring a job plan.</p>
              </div>
              <button
                className="button button--overview-action button--with-icon"
                type="button"
                onClick={() => {
                  setError(null)
                  setEditorTarget('new')
                }}
              >
                <AppIcon name="plus" />
                <span>Add Leave Year</span>
              </button>
            </div>
          ) : selectedLeaveYear ? (
            <div className="year-dashboard">
              <section
                className="dashboard-panel leave-year-summary"
                aria-labelledby="year-summary-title"
              >
                <header className="dashboard-panel-header leave-year-header">
                  <h4 id="year-summary-title">Leave Year</h4>
                  <div className="dashboard-panel-actions">
                    <button
                      className="button button--quiet overview-delete-button"
                      type="button"
                      onClick={beginRemoval}
                    >
                      Delete
                    </button>
                    <button
                      className="button button--overview-action button--with-icon"
                      type="button"
                      onClick={() => setEditorTarget(selectedLeaveYear)}
                    >
                      <AppIcon name="edit" />
                      <span>Edit</span>
                    </button>
                    <button
                      className="button button--overview-action button--with-icon"
                      type="button"
                      onClick={() => {
                        setError(null)
                        setEditorTarget('new')
                      }}
                    >
                      <AppIcon name="plus" />
                      <span>Add Year</span>
                    </button>
                  </div>
                  {leaveYears.length > 1 ? (
                    <label className="leave-year-selector">
                      <span className="visually-hidden">Selected Leave Year</span>
                      <select
                        value={selectedLeaveYear.id}
                        onChange={(event) => setSelectedId(Number(event.target.value))}
                      >
                        {leaveYears.map((leaveYear) => (
                          <option key={leaveYear.id} value={leaveYear.id}>
                            {formatDate(leaveYear.start_date)} - {formatDate(leaveYear.end_date)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                </header>

                <div className="leave-year-context">
                  <div className="leave-year-range">
                    <div>
                      <span>Start Date</span>
                      <time dateTime={selectedLeaveYear.start_date}>
                        {formatDate(selectedLeaveYear.start_date)}
                      </time>
                    </div>
                    <div>
                      <span>End Date</span>
                      <time dateTime={selectedLeaveYear.end_date}>
                        {formatDate(selectedLeaveYear.end_date)}
                      </time>
                    </div>
                  </div>

                  {selectedLeaveYear.employment_start || selectedLeaveYear.employment_end ? (
                    <dl>
                      {selectedLeaveYear.employment_start ? (
                        <div>
                          <dt>Employment From</dt>
                          <dd>{formatDate(selectedLeaveYear.employment_start)}</dd>
                        </div>
                      ) : null}
                      {selectedLeaveYear.employment_end ? (
                        <div>
                          <dt>Employment Until</dt>
                          <dd>{formatDate(selectedLeaveYear.employment_end)}</dd>
                        </div>
                      ) : null}
                    </dl>
                  ) : null}
                </div>

                <CarryForwardControl
                  consultantId={consultantId}
                  leaveYearId={selectedLeaveYear.id}
                  onSaved={refreshSummary}
                />
                <LeaveBalanceSummary summary={selectedSummary} error={summaryError} />
              </section>

              <JobPlanPanel
                key={selectedLeaveYear.id}
                consultantId={consultantId}
                leaveYear={selectedLeaveYear}
                onSaved={() => {
                  setCalculationRevision((revision) => revision + 1)
                  refreshSummary()
                }}
                onRemoved={() => {
                  setEntitlementReloadRevision((revision) => revision + 1)
                  refreshSummary()
                }}
              />
              <EntitlementPanel
                key={`entitlement-${selectedLeaveYear.id}`}
                consultantId={consultantId}
                leaveYearId={selectedLeaveYear.id}
                onChanged={refreshSummary}
                refreshRevision={calculationRevision}
                reloadRevision={entitlementReloadRevision}
              />
              {selectedSummary ? <ConsultantYearSummarySections summary={selectedSummary} /> : null}
            </div>
          ) : null}
        </>
      )}

      {editorTarget ? (
        <ModalLayer onClose={closeEditor}>
          <div className="modal-backdrop">
            <section
              className="record-modal record-modal--lined"
              role="dialog"
              aria-modal="true"
              aria-labelledby="leave-year-form-title"
              tabIndex={-1}
            >
              <button
                className="modal-close"
                type="button"
                aria-label="Close Leave Year Editor"
                disabled={saving}
                onClick={closeEditor}
              >
                x
              </button>

              {error ? (
                <p className="form-notice form-notice--error" role="alert">
                  {error}
                </p>
              ) : null}

              <LeaveYearForm
                key={editorTarget === 'new' ? 'new' : editorTarget.id}
                initialValue={
                  editorTarget === 'new' ? emptyLeaveYearInput() : editableValue(editorTarget)
                }
                mode={editorTarget === 'new' ? 'create' : 'edit'}
                busy={saving}
                onSubmit={saveLeaveYear}
                onCancel={closeEditor}
              />
            </section>
          </div>
        </ModalLayer>
      ) : null}

      {removalImpact ? (
        <RemovalDialog
          title="Delete Leave Year"
          impact={removalImpact}
          busy={removing}
          error={removalError}
          onConfirm={confirmRemoval}
          onCancel={() => {
            if (!removing) {
              setRemovalImpact(null)
              setRemovalError(null)
            }
          }}
        />
      ) : null}
    </section>
  )
}

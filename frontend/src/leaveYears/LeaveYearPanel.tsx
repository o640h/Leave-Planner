import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { JobPlanPanel } from '../jobPlans/JobPlanPanel'
import { AppIcon } from '../system/AppIcon'
import { createLeaveYear, listLeaveYears, updateLeaveYear } from './api'
import { LeaveYearForm } from './LeaveYearForm'
import { emptyLeaveYearInput, type LeaveYear, type LeaveYearInput } from './types'
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
  const [jobPlanCount, setJobPlanCount] = useState<number | null>(null)

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

  return (
    <section className="leave-year-panel" aria-labelledby="leave-years-title">
      <header className="leave-year-heading">
        <div>
          <h3 id="leave-years-title">Overview</h3>
        </div>
        <button
          className="icon-text-button"
          type="button"
          onClick={() => {
            setError(null)
            setEditorTarget('new')
          }}
        >
          <AppIcon name="plus" />
          <span>Add Leave Year</span>
        </button>
      </header>

      {notice ? (
        <p className="form-notice form-notice--success" role="status">
          {notice}
        </p>
      ) : null}

      {loading ? (
        <p className="leave-year-message">Loading leave years…</p>
      ) : error && editorTarget === null ? (
        <div className="leave-year-message form-notice--error" role="alert">
          <p>{error}</p>
          <button className="text-button" type="button" onClick={retryLoading}>
            Try Again
          </button>
        </div>
      ) : (
        <>
          <div className="workspace-overview" aria-label="Consultant Setup Overview">
            <div className={`overview-item${selectedLeaveYear ? '' : ' overview-item--warning'}`}>
              <AppIcon name="brand" />
              <div>
                <span>Leave Year</span>
                <strong>
                  {selectedLeaveYear
                    ? `${formatDate(selectedLeaveYear.start_date)} – ${formatDate(selectedLeaveYear.end_date)}`
                    : 'Not Configured'}
                </strong>
              </div>
            </div>
            <div
              className={`overview-item${jobPlanCount === 0 ? ' overview-item--warning' : jobPlanCount ? ' overview-item--complete' : ''}`}
            >
              <AppIcon name="jobPlan" />
              <div>
                <span>Job Plan</span>
                <strong>
                  {selectedLeaveYear === null
                    ? 'Requires Leave Year'
                    : jobPlanCount === null
                      ? 'Checking'
                      : jobPlanCount === 0
                        ? 'Not Configured'
                        : `${jobPlanCount} ${jobPlanCount === 1 ? 'Plan' : 'Plans'} Configured`}
                </strong>
              </div>
            </div>
          </div>

          {leaveYears.length === 0 ? (
            <div className="dashboard-empty">
              <div>
                <h4>No Leave Year Configured</h4>
                <p>Add the consultant's annual leave period before configuring a job plan.</p>
              </div>
            </div>
          ) : selectedLeaveYear ? (
            <div className="year-dashboard">
              <section
                className="dashboard-panel leave-year-summary"
                aria-labelledby="year-summary-title"
              >
                <header className="dashboard-panel-header">
                  <div>
                    <h4 id="year-summary-title">Current Leave Year</h4>
                  </div>
                  <div className="dashboard-panel-actions">
                    {leaveYears.length > 1 ? (
                      <select
                        aria-label="Selected Leave Year"
                        value={selectedLeaveYear.id}
                        onChange={(event) => {
                          setJobPlanCount(null)
                          setSelectedId(Number(event.target.value))
                        }}
                      >
                        {leaveYears.map((leaveYear) => (
                          <option key={leaveYear.id} value={leaveYear.id}>
                            {formatDate(leaveYear.start_date)} – {formatDate(leaveYear.end_date)}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    <button
                      className="button button--quiet button--with-icon"
                      type="button"
                      onClick={() => setEditorTarget(selectedLeaveYear)}
                    >
                      <AppIcon name="edit" />
                      <span>Edit</span>
                    </button>
                  </div>
                </header>

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

                <dl>
                  <div>
                    <dt>Employment From</dt>
                    <dd>
                      {selectedLeaveYear.employment_start
                        ? formatDate(selectedLeaveYear.employment_start)
                        : 'Covers Full Leave Year'}
                    </dd>
                  </div>
                  <div>
                    <dt>Employment Until</dt>
                    <dd>
                      {selectedLeaveYear.employment_end
                        ? formatDate(selectedLeaveYear.employment_end)
                        : 'Continues Beyond Leave Year'}
                    </dd>
                  </div>
                </dl>
              </section>

              <JobPlanPanel
                key={selectedLeaveYear.id}
                consultantId={consultantId}
                leaveYear={selectedLeaveYear}
                onCountChange={setJobPlanCount}
              />
            </div>
          ) : null}
        </>
      )}

      {editorTarget ? (
        <div className="modal-backdrop">
          <section
            className="record-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="leave-year-form-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Leave Year Editor"
              disabled={saving}
              onClick={closeEditor}
            >
              ×
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
      ) : null}
    </section>
  )
}

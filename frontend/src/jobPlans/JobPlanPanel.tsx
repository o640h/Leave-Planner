import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { LeaveYear } from '../leaveYears/types'
import { AppIcon } from '../system/AppIcon'
import { formatDecimal } from '../system/decimal'
import { createJobPlan, listJobPlans, previewJobPlan, updateJobPlan } from './api'
import { JobPlanForm } from './JobPlanForm'
import {
  editableJobPlan,
  emptyJobPlanInput,
  type JobPlan,
  type JobPlanInput,
  type JobPlanPreview,
} from './types'
import './jobPlans.css'

type EditorTarget = JobPlan | 'new' | null

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function sortJobPlans(jobPlans: JobPlan[]): JobPlan[] {
  return [...jobPlans].sort((first, second) =>
    first.effective_from.localeCompare(second.effective_from),
  )
}

type JobPlanPanelProps = {
  consultantId: number
  leaveYear: LeaveYear
  onCountChange?: (count: number | null) => void
}

export function JobPlanPanel({ consultantId, leaveYear, onCountChange }: JobPlanPanelProps) {
  const [jobPlans, setJobPlans] = useState<JobPlan[]>([])
  const [editorTarget, setEditorTarget] = useState<EditorTarget>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    onCountChange?.(null)
    listJobPlans(consultantId, leaveYear.id)
      .then((records) => {
        setJobPlans(sortJobPlans(records))
        onCountChange?.(records.length)
      })
      .catch((requestError: unknown) => {
        setError(operatorErrorMessage(requestError))
        onCountChange?.(null)
      })
      .finally(() => setLoading(false))
  }, [consultantId, leaveYear.id, loadAttempt, onCountChange])

  function retryLoading() {
    setLoading(true)
    setError(null)
    setLoadAttempt((attempt) => attempt + 1)
  }

  async function requestPreview(details: JobPlanInput): Promise<JobPlanPreview> {
    return previewJobPlan(consultantId, leaveYear.id, details)
  }

  async function saveJobPlan(details: JobPlanInput) {
    if (editorTarget === null) return

    setSaving(true)
    setError(null)
    setNotice(null)

    try {
      const saved =
        editorTarget === 'new'
          ? await createJobPlan(consultantId, leaveYear.id, details)
          : await updateJobPlan(consultantId, leaveYear.id, editorTarget.id, details)

      setJobPlans((current) => {
        const next =
          editorTarget === 'new'
            ? [...current, saved]
            : current.map((jobPlan) => (jobPlan.id === saved.id ? saved : jobPlan))

        return sortJobPlans(next)
      })

      setEditorTarget(null)
      setNotice(editorTarget === 'new' ? 'The job plan was created.' : 'The job plan was updated.')
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

  const initialValue =
    editorTarget === 'new'
      ? emptyJobPlanInput(leaveYear)
      : editorTarget
        ? editableJobPlan(editorTarget)
        : null

  return (
    <section className="dashboard-panel job-plan-panel" aria-labelledby="job-plans-title">
      <header className="dashboard-panel-header job-plan-heading">
        <div>
          <h4 id="job-plans-title">Job Plans</h4>
        </div>

        <button
          className="button button--quiet button--with-icon"
          type="button"
          onClick={() => {
            setError(null)
            setEditorTarget('new')
          }}
        >
          <AppIcon name="plus" />
          <span>Add Job Plan</span>
        </button>
      </header>

      {notice ? (
        <p className="form-notice form-notice--success" role="status">
          {notice}
        </p>
      ) : null}

      {loading ? (
        <p className="job-plan-message">Loading job plans…</p>
      ) : error && editorTarget === null ? (
        <div className="job-plan-message form-notice--error" role="alert">
          <p>{error}</p>
          <button className="text-button" type="button" onClick={retryLoading}>
            Try Again
          </button>
        </div>
      ) : jobPlans.length === 0 ? (
        <div className="job-plan-message job-plan-message--empty">
          <AppIcon name="jobPlan" />
          <p>No job plan is configured for this leave year.</p>
          <span>Add the overall PA split and weekday hours to continue setup.</span>
        </div>
      ) : (
        <div className="job-plan-list">
          {jobPlans.map((jobPlan, index) => (
            <article className="job-plan-card" key={jobPlan.id}>
              <header>
                <div>
                  <span className="job-plan-index">Job Plan {index + 1}</span>
                  <h4>
                    {formatDate(jobPlan.effective_from)}
                    {' — '}
                    {formatDate(jobPlan.effective_until)}
                  </h4>
                  <small>Effective Until is not included.</small>
                </div>

                <span
                  className={
                    jobPlan.reconciliation_override_reason
                      ? 'job-plan-status job-plan-status--warning'
                      : 'job-plan-status job-plan-status--nominal'
                  }
                >
                  {jobPlan.reconciliation_override_reason ? 'Saved With Override' : 'Reconciled'}
                </span>
              </header>

              <dl>
                <div>
                  <dt>Total PA</dt>
                  <dd>{formatDecimal(jobPlan.contracted_pas)}</dd>
                </div>
                <div>
                  <dt>DCC</dt>
                  <dd>{formatDecimal(jobPlan.dcc_pas)}</dd>
                </div>
                <div>
                  <dt>SPA</dt>
                  <dd>{formatDecimal(jobPlan.spa_pas)}</dd>
                </div>
                <div>
                  <dt>Pattern</dt>
                  <dd>
                    {jobPlan.week_count} {jobPlan.week_count === 1 ? 'Week' : 'Weeks'}
                  </dd>
                </div>
              </dl>

              <button
                className="button button--quiet"
                type="button"
                onClick={() => {
                  setError(null)
                  setEditorTarget(jobPlan)
                }}
              >
                Edit Job Plan
              </button>
            </article>
          ))}
        </div>
      )}

      {editorTarget && initialValue ? (
        <div className="modal-backdrop">
          <section
            className="record-modal job-plan-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-plan-form-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Job Plan Editor"
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

            <JobPlanForm
              key={editorTarget === 'new' ? 'new' : editorTarget.id}
              initialValue={initialValue}
              mode={editorTarget === 'new' ? 'create' : 'edit'}
              busy={saving}
              onPreview={requestPreview}
              onSubmit={saveJobPlan}
              onCancel={closeEditor}
            />
          </section>
        </div>
      ) : null}
    </section>
  )
}

import { useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { DateInput } from '../system/DateInput'
import { addNonNegativeDecimals, formatDecimal } from '../system/decimal'
import { NumberInput } from '../system/NumberInput'
import { JobPlanGrid } from './JobPlanGrid'
import { cycleDays, type JobPlanInput, type JobPlanPreview } from './types'

type JobPlanFormProps = {
  initialValue: JobPlanInput
  mode: 'create' | 'edit'
  busy: boolean
  onPreview: (details: JobPlanInput) => Promise<JobPlanPreview>
  onSubmit: (details: JobPlanInput) => Promise<void>
  onCancel: () => void
}

export function JobPlanForm({
  initialValue,
  mode,
  busy,
  onPreview,
  onSubmit,
  onCancel,
}: JobPlanFormProps) {
  const [details, setDetails] = useState(initialValue)
  const [preview, setPreview] = useState<JobPlanPreview | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const disabled = busy || previewing

  function changeDetails(changes: Partial<JobPlanInput>) {
    setDetails((current) => {
      const next = { ...current, ...changes }

      if ('dcc_pas' in changes || 'spa_pas' in changes) {
        next.contracted_pas = addNonNegativeDecimals(next.dcc_pas, next.spa_pas)
      }

      return next
    })
    setPreview(null)
    setError(null)
  }

  function changeWeekCount(value: string) {
    const weekCount = Math.max(1, Number(value) || 1)

    setDetails((current) => ({
      ...current,
      week_count: weekCount,
      cycle_anchor_date: weekCount === 1 ? null : current.cycle_anchor_date,
      days: cycleDays(weekCount, current.days),
    }))
    setPreview(null)
    setError(null)
  }

  function changeDay(
    cycleWeek: number,
    weekday: number,
    field: 'dcc_hours' | 'spa_hours',
    value: string,
  ) {
    setDetails((current) => ({
      ...current,
      days: current.days.map((day) =>
        day.cycle_week === cycleWeek && day.weekday === weekday ? { ...day, [field]: value } : day,
      ),
    }))
    setPreview(null)
    setError(null)
  }

  function changeOverrideReason(value: string) {
    // The reason explains the current preview; changing it does not invalidate the maths.
    setDetails((current) => ({
      ...current,
      reconciliation_override_reason: value || null,
    }))
    setError(null)
  }

  function hasRequiredValues(): boolean {
    const decimalValues = [
      details.dcc_pas,
      details.spa_pas,
      details.hours_per_pa,
      ...details.days.flatMap((day) => [day.dcc_hours, day.spa_hours]),
    ]

    if (!details.effective_from || !details.effective_until) {
      setError('Enter the Effective From and Effective Until dates.')
      return false
    }

    if (details.effective_until <= details.effective_from) {
      setError('Effective Until must be after Effective From.')
      return false
    }

    if (decimalValues.some((value) => !value.trim())) {
      setError('Enter a value for every PA and hours field.')
      return false
    }

    return true
  }

  async function requestPreview(): Promise<JobPlanPreview | null> {
    if (!hasRequiredValues()) return null

    setPreviewing(true)
    setError(null)

    try {
      const result = await onPreview(details)
      setPreview(result)
      return result
    } catch (requestError) {
      setError(operatorErrorMessage(requestError))
      return null
    } finally {
      setPreviewing(false)
    }
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()

    const result = await requestPreview()
    if (!result) return

    if (!result.is_reconciled && !details.reconciliation_override_reason?.trim()) {
      setError('Explain why the activity PAs do not equal total contracted PAs.')
      return
    }

    await onSubmit(details)
  }

  return (
    <form className="job-plan-form" noValidate onSubmit={handleSubmit}>
      <div className="form-introduction">
        <span className="section-label">
          {mode === 'create' ? 'New Job Plan' : 'Selected Job Plan'}
        </span>

        <h3 id="job-plan-form-title">{mode === 'create' ? 'Add Job Plan' : 'Edit Job Plan'}</h3>

        <p>
          Overall PAs allocate entitlement. The weekday grid controls the hours deducted when leave
          falls on that day.
        </p>
      </div>

      {error ? (
        <p className="form-notice form-notice--error" role="alert">
          {error}
        </p>
      ) : null}

      <section className="job-plan-form-section">
        <header>
          <h4>Effective Period</h4>
          <p>Effective Until is not included in this job plan.</p>
        </header>

        <div className="job-plan-date-fields">
          <div className="field">
            <label htmlFor="job-plan-effective-from">Effective From</label>
            <DateInput
              id="job-plan-effective-from"
              label="Effective From"
              value={details.effective_from}
              disabled={disabled}
              onChange={(value) => changeDetails({ effective_from: value })}
            />
          </div>

          <div className="field">
            <label htmlFor="job-plan-effective-until">Effective Until</label>
            <DateInput
              id="job-plan-effective-until"
              label="Effective Until"
              value={details.effective_until}
              disabled={disabled}
              onChange={(value) => changeDetails({ effective_until: value })}
            />
          </div>
        </div>
      </section>

      <section className="job-plan-form-section">
        <header>
          <h4>Contracted PAs</h4>
          <p>Total PA is calculated from DCC and SPA.</p>
        </header>

        <div className="job-plan-pa-fields">
          <div className="field">
            <label htmlFor="job-plan-contracted-pas">Total PA</label>
            <output className="calculated-field" id="job-plan-contracted-pas">
              {formatDecimal(details.contracted_pas, 2) || '-'}
            </output>
          </div>

          {(
            [
              ['dcc_pas', 'DCC PAs'],
              ['spa_pas', 'SPA PAs'],
            ] as const
          ).map(([field, label]) => (
            <div className="field" key={field}>
              <label htmlFor={`job-plan-${field}`}>{label}</label>
              <NumberInput
                id={`job-plan-${field}`}
                label={label}
                min="0"
                step="0.01"
                inputMode="decimal"
                value={details[field]}
                disabled={disabled}
                onChange={(value) => changeDetails({ [field]: value })}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="job-plan-form-section">
        <header>
          <h4>Working Pattern</h4>
          <p>
            Most consultants use one week. Increase this only for a repeating multi-week pattern.
          </p>
        </header>

        <div className="job-plan-cycle-fields">
          <div className="field field--week-count">
            <label htmlFor="job-plan-week-count">Number of Weeks</label>
            <NumberInput
              id="job-plan-week-count"
              label="Number of Weeks"
              min="1"
              step="1"
              inputMode="numeric"
              value={details.week_count}
              disabled={disabled}
              onChange={changeWeekCount}
            />
          </div>

          {details.week_count > 1 ? (
            <div className="field">
              <label htmlFor="job-plan-cycle-anchor">Week 1 Monday</label>
              <DateInput
                id="job-plan-cycle-anchor"
                label="Week 1 Monday"
                value={details.cycle_anchor_date ?? ''}
                disabled={disabled}
                onChange={(value) =>
                  changeDetails({
                    cycle_anchor_date: value || null,
                  })
                }
              />
              <small>Optional - otherwise the Monday before Effective From is used.</small>
            </div>
          ) : null}
        </div>

        <JobPlanGrid
          weekCount={details.week_count}
          days={details.days}
          disabled={disabled}
          onChange={changeDay}
        />
      </section>

      <details className="job-plan-advanced">
        <summary>Advanced Settings</summary>

        <div className="field">
          <label htmlFor="job-plan-hours-per-pa">Hours per PA</label>
          <NumberInput
            id="job-plan-hours-per-pa"
            label="Hours per PA"
            min="0.001"
            step="0.25"
            inputMode="decimal"
            value={details.hours_per_pa}
            disabled={disabled}
            onChange={(value) => changeDetails({ hours_per_pa: value })}
          />
          <small>The normal consultant value is four hours.</small>
        </div>
      </details>

      <div className="job-plan-preview-actions">
        <button
          className="button button--quiet"
          type="button"
          disabled={disabled}
          onClick={() => void requestPreview()}
        >
          {previewing ? 'Calculating...' : 'Preview Job Plan'}
        </button>
      </div>

      {preview ? (
        <section
          className={`job-plan-preview ${
            preview.is_reconciled ? 'job-plan-preview--nominal' : 'job-plan-preview--warning'
          }`}
          aria-live="polite"
        >
          <header>
            <span className="section-label">Calculation Preview</span>
            <h4>{preview.is_reconciled ? 'PA Split Reconciled' : 'Override Required'}</h4>
          </header>

          <dl>
            <div>
              <dt>Contracted PAs</dt>
              <dd>{formatDecimal(preview.contracted_pas, 2)}</dd>
            </div>
            <div>
              <dt>Allocated PAs</dt>
              <dd>{formatDecimal(preview.allocated_pas, 2)}</dd>
            </div>
            <div>
              <dt>Difference</dt>
              <dd>{formatDecimal(preview.reconciliation_variance, 2)}</dd>
            </div>
            <div>
              <dt>Visible Hours per Week</dt>
              <dd>{formatDecimal(preview.average_visible_hours, 2)}</dd>
            </div>
          </dl>

          {preview.warning ? <p>{preview.warning}</p> : null}
        </section>
      ) : null}

      {preview && !preview.is_reconciled ? (
        <div className="field job-plan-override">
          <label htmlFor="job-plan-override-reason">Reconciliation Override Reason</label>
          <textarea
            id="job-plan-override-reason"
            rows={3}
            value={details.reconciliation_override_reason ?? ''}
            disabled={disabled}
            onChange={(event) => changeOverrideReason(event.target.value)}
          />
        </div>
      ) : null}

      <div className="form-actions">
        <button
          className="button button--quiet"
          type="button"
          disabled={disabled}
          onClick={onCancel}
        >
          Cancel
        </button>

        <button className="button button--primary" type="submit" disabled={disabled}>
          {busy ? 'Saving...' : mode === 'create' ? 'Create Job Plan' : 'Save Changes'}
        </button>
      </div>
    </form>
  )
}

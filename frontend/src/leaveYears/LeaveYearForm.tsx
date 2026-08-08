import { useState } from 'react'
import type { SubmitEvent } from 'react'

import type { LeaveYearInput } from './types'

type LeaveYearFormProps = {
  initialValue: LeaveYearInput
  mode: 'create' | 'edit'
  busy: boolean
  onSubmit: (details: LeaveYearInput) => Promise<void>
  onCancel: () => void
}

export function LeaveYearForm({
  initialValue,
  mode,
  busy,
  onSubmit,
  onCancel,
}: LeaveYearFormProps) {
  const [details, setDetails] = useState(initialValue)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!details.start_date || !details.end_date) {
      setError('Enter the leave year start and end dates.')
      return
    }

    if (details.end_date < details.start_date) {
      setError('The leave-year end must not be before its start.')
      return
    }

    setError(null)
    await onSubmit(details)
  }

  function updateDate(field: keyof LeaveYearInput, value: string, optional = false) {
    setError(null)
    setDetails((current) => ({
      ...current,
      [field]: optional && !value ? null : value,
    }))
  }

  return (
    <form className="leave-year-form" noValidate onSubmit={handleSubmit}>
      <div className="form-introduction">
        <span className="section-label">
          {mode === 'create' ? 'New Leave Year' : 'Selected Leave Year'}
        </span>
        <h3 id="leave-year-form-title">
          {mode === 'create' ? 'Add Leave Year' : 'Edit Leave Year'}
        </h3>
        <p>
          Leave-year dates are inclusive. Only enter employment dates when employment starts or ends
          during this leave year.
        </p>
      </div>

      {error ? (
        <p className="form-notice form-notice--error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="leave-year-fields">
        <div className="field">
          <label htmlFor="leave-year-start">Annual Leave Year Start</label>
          <input
            id="leave-year-start"
            type="date"
            value={details.start_date}
            aria-required="true"
            disabled={busy}
            onChange={(event) => updateDate('start_date', event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="leave-year-end">Annual Leave Year End</label>
          <input
            id="leave-year-end"
            type="date"
            value={details.end_date}
            aria-required="true"
            disabled={busy}
            onChange={(event) => updateDate('end_date', event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="employment-start">Employment Start</label>
          <input
            id="employment-start"
            type="date"
            value={details.employment_start ?? ''}
            disabled={busy}
            onChange={(event) => updateDate('employment_start', event.target.value, true)}
          />
          <small>Optional — leave blank when employment covers the full year.</small>
        </div>

        <div className="field">
          <label htmlFor="employment-end">Employment End</label>
          <input
            id="employment-end"
            type="date"
            value={details.employment_end ?? ''}
            disabled={busy}
            onChange={(event) => updateDate('employment_end', event.target.value, true)}
          />
          <small>Optional — leave blank when employment continues.</small>
        </div>
      </div>

      <div className="form-actions">
        <button className="button button--quiet" type="button" disabled={busy} onClick={onCancel}>
          Cancel
        </button>

        <button className="button button--primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : mode === 'create' ? 'Create Leave Year' : 'Save Changes'}
        </button>
      </div>
    </form>
  )
}

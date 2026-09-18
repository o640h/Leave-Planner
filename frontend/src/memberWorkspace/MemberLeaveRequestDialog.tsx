import { useEffect, useState, type SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import type { LeavePreview } from '../planning/types'
import { DateInput } from '../system/DateInput'
import { formatDecimal } from '../system/decimal'
import { ModalLayer } from '../system/ModalLayer'
import type { MemberLeaveRequestInput } from './api'

type Props = {
  initialDate?: string | null
  busy: boolean
  onPreview: (details: MemberLeaveRequestInput) => Promise<LeavePreview>
  onSubmit: (details: MemberLeaveRequestInput) => Promise<void>
  onClose: () => void
}

export function MemberLeaveRequestDialog({
  initialDate = null,
  busy,
  onPreview,
  onSubmit,
  onClose,
}: Props) {
  const [details, setDetails] = useState<MemberLeaveRequestInput>({
    start_date: initialDate ?? '',
    end_date: initialDate ?? '',
    note: null,
  })
  const [preview, setPreview] = useState<LeavePreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!details.start_date || !details.end_date || details.end_date < details.start_date) {
      return
    }
    let active = true
    onPreview(details)
      .then((result) => {
        if (!active) return
        setPreview(result)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setPreview(null)
        setError(operatorErrorMessage(reason))
      })
    return () => {
      active = false
    }
  }, [details, onPreview])

  const datesValid = Boolean(
    details.start_date && details.end_date && details.end_date >= details.start_date,
  )
  const visiblePreview = datesValid ? preview : null

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!visiblePreview) return
    try {
      await onSubmit(details)
    } catch (reason) {
      setError(operatorErrorMessage(reason))
    }
  }

  return (
    <ModalLayer onClose={busy ? () => undefined : onClose}>
      <div className="planning-drawer-backdrop member-request-backdrop" role="presentation">
        <section
          className="record-modal member-request-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="member-request-title"
        >
          <header>
            <div>
              <span className="section-kicker">Leave Request</span>
              <h2 id="member-request-title">Request Leave</h2>
              <p>Your request will be sent to the workspace team for review.</p>
            </div>
            <button className="modal-close" type="button" aria-label="Close" onClick={onClose}>
              X
            </button>
          </header>
          <form noValidate onSubmit={submit}>
            {error ? <p className="form-notice form-notice--error">{error}</p> : null}
            <div className="member-request-fields">
              <label htmlFor="member-request-start">
                <span>Start Date</span>
                <DateInput
                  id="member-request-start"
                  label="Start Date"
                  value={details.start_date}
                  disabled={busy}
                  onChange={(start_date) => setDetails((current) => ({ ...current, start_date }))}
                />
              </label>
              <label htmlFor="member-request-end">
                <span>End Date</span>
                <DateInput
                  id="member-request-end"
                  label="End Date"
                  value={details.end_date}
                  disabled={busy}
                  onChange={(end_date) => setDetails((current) => ({ ...current, end_date }))}
                />
              </label>
              <label className="member-request-note">
                <span>Note (Optional)</span>
                <input
                  maxLength={500}
                  value={details.note ?? ''}
                  disabled={busy}
                  onChange={(event) =>
                    setDetails((current) => ({ ...current, note: event.target.value || null }))
                  }
                />
              </label>
            </div>
            {visiblePreview ? (
              <section className="member-request-preview" aria-label="Request preview">
                <div>
                  <span>Working Days</span>
                  <strong>
                    {visiblePreview.days.filter((day) => day.deduction.total_hours !== '0').length}
                  </strong>
                </div>
                <div>
                  <span>Requested Remaining</span>
                  <strong>
                    {visiblePreview.requested
                      ? `${formatDecimal(visiblePreview.requested.remaining.total_hours, 2)}h`
                      : 'Not Available'}
                  </strong>
                </div>
                {visiblePreview.warnings.length ? (
                  <div className="member-request-warnings">
                    {visiblePreview.warnings.map((warning) => (
                      <p key={`${warning.code}-${warning.message}`}>{warning.message}</p>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}
            <footer className="form-actions">
              <button className="button" type="button" disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button
                className="button button--primary"
                type="submit"
                disabled={busy || !visiblePreview}
              >
                Submit Request
              </button>
            </footer>
          </form>
        </section>
      </div>
    </ModalLayer>
  )
}

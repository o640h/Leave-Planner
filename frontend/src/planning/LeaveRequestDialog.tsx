import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { formatDecimal } from '../system/decimal'
import { ModalLayer } from '../system/ModalLayer'
import { getLeaveRequestReview, type LeaveRequestDecision } from './api'
import type { LeaveRequestQueue, LeaveRequestQueueItem, LeaveRequestReview } from './types'

type Props = {
  queue: LeaveRequestQueue
  initialRequest?: LeaveRequestQueueItem | null
  busy: boolean
  onDecide: (request: LeaveRequestQueueItem, decision: LeaveRequestDecision) => Promise<void>
  onClose: () => void
}

const dates = (start: string, end: string) => {
  const format = (value: string) =>
    new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  return `${format(start)} - ${format(end)}`
}

export function LeaveRequestDialog({ queue, initialRequest, busy, onDecide, onClose }: Props) {
  const [selected, setSelected] = useState<LeaveRequestQueueItem | null>(
    initialRequest ?? queue.requests[0] ?? null,
  )
  const [review, setReview] = useState<LeaveRequestReview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selected) return
    let active = true
    getLeaveRequestReview(selected.consultant_id, selected.leave_year_id, selected.booking_id)
      .then((result) => {
        if (!active) return
        setReview(result)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!active) return
        setError(operatorErrorMessage(reason))
      })
    return () => {
      active = false
    }
  }, [selected])

  const isCancellation = selected?.kind === 'cancellation_request'
  return (
    <ModalLayer onClose={busy ? () => undefined : onClose}>
      <div className="planning-drawer-backdrop request-review-backdrop" role="presentation">
        <section
          className="request-review-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="request-review-title"
        >
          <header>
            <div>
              <span className="section-kicker">Member Requests</span>
              <h2 id="request-review-title">Review Leave</h2>
            </div>
            <button className="modal-close" type="button" aria-label="Close" onClick={onClose}>
              X
            </button>
          </header>
          <div className="request-review-layout">
            <aside className="request-queue" aria-label="Pending requests">
              {queue.requests.length ? (
                queue.requests.map((request) => (
                  <button
                    className={
                      selected?.booking_id === request.booking_id
                        ? 'request-queue-item request-queue-item--active'
                        : 'request-queue-item'
                    }
                    type="button"
                    key={request.booking_id}
                    onClick={() => {
                      if (selected?.booking_id === request.booking_id) return
                      setReview(null)
                      setError(null)
                      setSelected(request)
                    }}
                  >
                    <strong>{request.consultant_name}</strong>
                    <span>
                      {request.kind === 'cancellation_request'
                        ? 'Cancellation Request'
                        : 'Leave Request'}
                    </span>
                    <small>{dates(request.start_date, request.end_date)}</small>
                  </button>
                ))
              ) : (
                <p>No requests are waiting for review.</p>
              )}
            </aside>
            <main className="request-review-content">
              {error ? (
                <p className="form-notice form-notice--error">{error}</p>
              ) : !selected ? (
                <p className="request-review-empty">Select a request to review its effect.</p>
              ) : !review ? (
                <p className="request-review-empty">Calculating balance effect...</p>
              ) : (
                <>
                  <div className="request-review-heading">
                    <div>
                      <span>{isCancellation ? 'Cancellation Request' : 'Leave Request'}</span>
                      <h3>{selected.consultant_name}</h3>
                      <p>{dates(selected.start_date, selected.end_date)}</p>
                    </div>
                    <span>
                      {review.days.length} {review.days.length === 1 ? 'Day' : 'Days'}
                    </span>
                  </div>
                  {selected.note ? <p className="request-review-note">{selected.note}</p> : null}
                  <div className="request-balance-effect">
                    <div>
                      <span>Approved Remaining Now</span>
                      <strong>
                        {review.current_approved
                          ? `${formatDecimal(review.current_approved.remaining.total_hours, 2)}h`
                          : 'Not Available'}
                      </strong>
                    </div>
                    <div>
                      <span>After {isCancellation ? 'Cancellation' : 'Approval'}</span>
                      <strong>
                        {review.resulting_approved
                          ? `${formatDecimal(review.resulting_approved.remaining.total_hours, 2)}h`
                          : 'Not Available'}
                      </strong>
                    </div>
                  </div>
                  {review.warnings.length ? (
                    <div className="booking-warnings">
                      {review.warnings.map((warning) => (
                        <p key={`${warning.code}-${warning.message}`}>{warning.message}</p>
                      ))}
                    </div>
                  ) : null}
                  <footer className="form-actions">
                    <button
                      className="button"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void onDecide(selected, isCancellation ? 'reject-cancellation' : 'reject')
                      }
                    >
                      {isCancellation ? 'Keep Approved' : 'Reject Request'}
                    </button>
                    <button
                      className="button button--primary"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void onDecide(selected, isCancellation ? 'approve-cancellation' : 'approve')
                      }
                    >
                      {isCancellation ? 'Approve Cancellation' : 'Approve Request'}
                    </button>
                  </footer>
                </>
              )}
            </main>
          </div>
          {queue.recent_activity.length ? (
            <details className="request-activity">
              <summary>Recent Request Activity</summary>
              {queue.recent_activity.map((event) => (
                <p key={event.id}>
                  <strong>{event.consultant_name}</strong>
                  <span>{event.event_type.replaceAll('_', ' ')}</span>
                  <small>{event.actor_label}</small>
                </p>
              ))}
            </details>
          ) : null}
        </section>
      </div>
    </ModalLayer>
  )
}

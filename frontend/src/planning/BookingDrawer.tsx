import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'

import { operatorErrorMessage } from '../api/client'
import { DateInput } from '../system/DateInput'
import { addNonNegativeDecimals, formatDecimal } from '../system/decimal'
import { NumberInput } from '../system/NumberInput'
import type {
  DailyOverrideInput,
  LeaveBooking,
  LeaveBookingInput,
  LeaveDay,
  LeavePreview,
  LeaveState,
} from './types'

type Props = {
  consultantName: string
  booking: LeaveBooking | null
  initialDate: string | null
  busy: boolean
  onPreview: (details: LeaveBookingInput, bookingId?: number) => Promise<LeavePreview>
  onSave: (details: LeaveBookingInput, bookingId?: number) => Promise<void>
  onCancelBooking: (bookingId: number) => Promise<void>
  onClose: () => void
}

type OverrideDraft = { dcc: string; spa: string; other: string; reason: string }

const emptyInput = (date: string | null): LeaveBookingInput => ({
  start_date: date ?? '',
  end_date: date ?? '',
  state: 'planned',
  note: null,
  overrides: [],
})

function bookingDrafts(booking: LeaveBooking | null): Record<string, OverrideDraft> {
  if (!booking) return {}
  return Object.fromEntries(
    booking.days.map((day) => [
      day.leave_date,
      {
        dcc: formatDecimal(day.deduction.dcc_hours, 2),
        spa: formatDecimal(day.deduction.spa_hours, 2),
        other: formatDecimal(day.deduction.other_hours, 2),
        reason: day.override_reason ?? '',
      },
    ]),
  )
}

function bookingOverrides(booking: LeaveBooking | null): DailyOverrideInput[] {
  if (!booking) return []
  return booking.days.flatMap((day) => {
    const changed =
      formatDecimal(day.deduction.dcc_hours) !== formatDecimal(day.standard.dcc_hours) ||
      formatDecimal(day.deduction.spa_hours) !== formatDecimal(day.standard.spa_hours) ||
      formatDecimal(day.deduction.other_hours) !== formatDecimal(day.standard.other_hours)
    return changed
      ? [
          {
            leave_date: day.leave_date,
            dcc_hours: formatDecimal(day.deduction.dcc_hours, 2),
            spa_hours: formatDecimal(day.deduction.spa_hours, 2),
            other_hours: formatDecimal(day.deduction.other_hours, 2),
            reason: day.override_reason,
          },
        ]
      : []
  })
}

export function BookingDrawer({
  consultantName,
  booking,
  initialDate,
  busy,
  onPreview,
  onSave,
  onCancelBooking,
  onClose,
}: Props) {
  const [details, setDetails] = useState<LeaveBookingInput>(() =>
    booking
      ? {
          start_date: booking.start_date,
          end_date: booking.end_date,
          state: booking.state,
          note: booking.note,
          overrides: bookingOverrides(booking),
        }
      : emptyInput(initialDate),
  )
  const [preview, setPreview] = useState<LeavePreview | null>(null)
  const [drafts, setDrafts] = useState<Record<string, OverrideDraft>>(() => bookingDrafts(booking))
  const [error, setError] = useState<string | null>(null)

  function overrideInputs(days: LeaveDay[]): DailyOverrideInput[] {
    return days.flatMap((day) => {
      const draft = drafts[day.leave_date]
      if (!draft) return []
      const changed =
        formatDecimal(draft.dcc) !== formatDecimal(day.standard.dcc_hours) ||
        formatDecimal(draft.spa) !== formatDecimal(day.standard.spa_hours) ||
        formatDecimal(draft.other) !== formatDecimal(day.standard.other_hours)
      if (!changed) return []
      return [
        {
          leave_date: day.leave_date,
          dcc_hours: draft.dcc,
          spa_hours: draft.spa,
          other_hours: draft.other,
          reason: draft.reason.trim() || null,
        },
      ]
    })
  }

  useEffect(() => {
    if (!details.start_date || !details.end_date) return

    let active = true
    void onPreview(
      {
        start_date: details.start_date,
        end_date: details.end_date,
        state: details.state,
        note: null,
        overrides: details.overrides,
      },
      booking?.id,
    )
      .then((result) => {
        if (!active) return
        setError(null)
        setPreview(result)
        setDrafts(
          Object.fromEntries(
            result.days.map((day) => [
              day.leave_date,
              {
                dcc: formatDecimal(day.deduction.dcc_hours, 2),
                spa: formatDecimal(day.deduction.spa_hours, 2),
                other: formatDecimal(day.deduction.other_hours, 2),
                reason: day.override_reason ?? '',
              },
            ]),
          ),
        )
      })
      .catch((caught: unknown) => {
        if (active) setError(operatorErrorMessage(caught))
      })

    return () => {
      active = false
    }
  }, [
    booking?.id,
    details.end_date,
    details.overrides,
    details.start_date,
    details.state,
    onPreview,
  ])

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!preview) return
    const overrides = overrideInputs(preview.days)
    try {
      await onSave({ ...details, overrides }, booking?.id)
    } catch (caught) {
      setError(operatorErrorMessage(caught))
    }
  }

  function changeDraft(date: string, changes: Partial<OverrideDraft>) {
    setDrafts((current) => ({
      ...current,
      [date]: { ...current[date], ...changes },
    }))
  }

  const disabled = busy
  const deductionTotal = preview?.days.reduce((total, day) => {
    const draft = drafts[day.leave_date]
    const dayTotal = addNonNegativeDecimals(
      addNonNegativeDecimals(
        draft?.dcc ?? day.deduction.dcc_hours,
        draft?.spa ?? day.deduction.spa_hours,
      ),
      draft?.other ?? day.deduction.other_hours,
    )
    return addNonNegativeDecimals(total, dayTotal)
  }, '0')

  return (
    <div className="planning-drawer-backdrop" role="presentation">
      <aside className="booking-drawer" aria-labelledby="booking-title">
        <header>
          <div>
            <span className="section-kicker">Leave Booking</span>
            <h2 id="booking-title">{booking ? 'Edit Leave' : 'Book Leave'}</h2>
            <p className="booking-consultant">{consultantName}</p>
          </div>
          <button className="modal-close" type="button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>

        <form noValidate onSubmit={submit}>
          {error && <div className="form-notice form-notice--error">{error}</div>}
          <div className="booking-fields">
            <label>
              <span>Start Date</span>
              <DateInput
                id="booking-start"
                label="Start Date"
                value={details.start_date}
                disabled={disabled}
                onChange={(start_date) => {
                  setDetails((current) => ({ ...current, start_date, overrides: [] }))
                  setDrafts({})
                  setPreview(null)
                }}
              />
            </label>
            <label>
              <span>End Date</span>
              <DateInput
                id="booking-end"
                label="End Date"
                value={details.end_date}
                disabled={disabled}
                onChange={(end_date) => {
                  setDetails((current) => ({ ...current, end_date, overrides: [] }))
                  setDrafts({})
                  setPreview(null)
                }}
              />
            </label>
            <label>
              <span>Status</span>
              <select
                value={details.state}
                disabled={disabled}
                onChange={(event) => {
                  const overrides = preview ? overrideInputs(preview.days) : details.overrides
                  setDetails((current) => ({
                    ...current,
                    state: event.target.value as LeaveState,
                    overrides,
                  }))
                  setPreview(null)
                }}
              >
                <option value="planned">Planned</option>
                <option value="approved">Approved</option>
                <option value="taken">Taken</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
            <label className="booking-note">
              <span>Note</span>
              <input
                value={details.note ?? ''}
                maxLength={500}
                disabled={disabled}
                onChange={(event) =>
                  setDetails((current) => ({ ...current, note: event.target.value || null }))
                }
              />
            </label>
          </div>

          {preview && (
            <section className="deduction-preview" aria-labelledby="deduction-title">
              <div className="deduction-heading">
                <h3 id="deduction-title">Daily Deductions</h3>
                <span>{formatDecimal(deductionTotal ?? '0', 2)} hours</span>
              </div>
              {preview.warnings.some(
                (warning) => warning.code !== 'leave-balance.carry-forward',
              ) && (
                <div className="booking-warnings">
                  {preview.warnings
                    .filter((warning) => warning.code !== 'leave-balance.carry-forward')
                    .map((warning) => (
                      <p key={`${warning.code}-${warning.message}`}>{warning.message}</p>
                    ))}
                </div>
              )}
              <div className="deduction-table">
                <div className="deduction-row deduction-row--heading">
                  <span>Date</span>
                  <span>DCC</span>
                  <span>SPA</span>
                  <span>Reason</span>
                </div>
                {preview.days.map((day) => {
                  const draft = drafts[day.leave_date]
                  return (
                    <div className="deduction-row" key={day.leave_date}>
                      <span>
                        {new Date(`${day.leave_date}T00:00:00`).toLocaleDateString('en-GB', {
                          weekday: 'short',
                          day: 'numeric',
                          month: 'short',
                        })}
                        {day.public_holiday_name && <small>{day.public_holiday_name}</small>}
                      </span>
                      <NumberInput
                        label={`DCC on ${day.leave_date}`}
                        value={draft?.dcc ?? day.deduction.dcc_hours}
                        min="0"
                        step="0.25"
                        disabled={disabled || Boolean(day.public_holiday_name)}
                        onChange={(dcc) => changeDraft(day.leave_date, { dcc })}
                      />
                      <NumberInput
                        label={`SPA on ${day.leave_date}`}
                        value={draft?.spa ?? day.deduction.spa_hours}
                        min="0"
                        step="0.25"
                        disabled={disabled || Boolean(day.public_holiday_name)}
                        onChange={(spa) => changeDraft(day.leave_date, { spa })}
                      />
                      <input
                        aria-label={`Replacement reason for ${day.leave_date}`}
                        placeholder="Optional"
                        value={draft?.reason ?? ''}
                        disabled={disabled || Boolean(day.public_holiday_name)}
                        onChange={(event) =>
                          changeDraft(day.leave_date, { reason: event.target.value })
                        }
                      />
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          <footer className="form-actions">
            {booking && booking.state !== 'cancelled' && (
              <button
                className="button button--danger"
                type="button"
                disabled={disabled}
                onClick={() => onCancelBooking(booking.id)}
              >
                Cancel Booking
              </button>
            )}
            <span className="form-action-spacer" />
            <button className="button" type="button" disabled={disabled} onClick={onClose}>
              Close
            </button>
            <button
              className="button button--primary"
              type="submit"
              disabled={disabled || !preview}
            >
              {booking ? 'Save Changes' : 'Save Booking'}
            </button>
          </footer>
        </form>
      </aside>
    </div>
  )
}

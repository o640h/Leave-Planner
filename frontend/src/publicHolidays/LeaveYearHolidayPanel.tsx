import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { formatDecimal } from '../system/decimal'
import { DateInput } from '../system/DateInput'
import { getLeaveYearHolidays, saveHolidayTreatment } from './api'
import type { HolidayOccurrence, HolidayTreatmentBasis, LeaveYearHolidays } from './types'
import './publicHolidays.css'

type Props = { consultantId: number; leaveYearId: number }

export function LeaveYearHolidayPanel({ consultantId, leaveYearId }: Props) {
  const [data, setData] = useState<LeaveYearHolidays | null>(null)
  const [editing, setEditing] = useState<HolidayOccurrence | null>(null)
  const [basis, setBasis] = useState<HolidayTreatmentBasis>('standard')
  const [note, setNote] = useState('')
  const [workedDate, setWorkedDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLeaveYearHolidays(consultantId, leaveYearId)
      .then(setData)
      .catch((e: unknown) => setError(operatorErrorMessage(e)))
  }, [consultantId, leaveYearId])

  function edit(item: HolidayOccurrence) {
    setEditing(item)
    setBasis(item.basis)
    setNote(item.treatment_note ?? '')
    setWorkedDate(item.worked_date ?? '')
  }
  async function save() {
    if (!editing) return
    try {
      setData(
        await saveHolidayTreatment(consultantId, leaveYearId, editing.holiday_date, {
          basis,
          note: note || null,
          worked_date: workedDate || null,
        }),
      )
      setEditing(null)
      setError(null)
    } catch (e) {
      setError(operatorErrorMessage(e))
    }
  }

  return (
    <section className="entitlement-holidays" aria-label="Public Holidays">
      {error ? <p className="form-notice form-notice--error">{error}</p> : null}
      {data ? (
        <details className="holiday-disclosure">
          <summary>Public Holidays ({data.occurrences.length})</summary>
          <div className="holiday-disclosure-summary">
            <span>
              Entitlement <strong>{formatDecimal(data.entitlement_hours, 3)}</strong>
            </span>
            <span>
              Standard Deductions <strong>{formatDecimal(data.deduction_hours, 3)}</strong>
            </span>
            <small>
              {data.source.replaceAll('_', ' ')} · {data.source_date}
            </small>
          </div>
          <ul>
            {data.occurrences.map((item) => (
              <li key={item.holiday_date}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.holiday_date}</span>
                </div>
                <span>
                  {formatDecimal(item.entitlement_hours, 3)} hours ·{' '}
                  {item.basis.replaceAll('_', ' ')}
                </span>
                <button className="text-button" type="button" onClick={() => edit(item)}>
                  Treatment
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {editing ? (
        <div className="modal-backdrop">
          <section
            className="record-modal adjustment-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="holiday-treatment-title"
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close Holiday Treatment"
              onClick={() => setEditing(null)}
            >
              ×
            </button>
            <header>
              <span className="section-label">{editing.holiday_date}</span>
              <h2 id="holiday-treatment-title">{editing.name}</h2>
            </header>
            <div className="field">
              <label htmlFor="holiday-basis">Treatment</label>
              <select
                id="holiday-basis"
                value={basis}
                onChange={(event) => setBasis(event.target.value as HolidayTreatmentBasis)}
              >
                <option value="standard">Not Worked — Standard Deduction</option>
                <option value="qualifying_on_call">On Call — Retain Leave</option>
              </select>
            </div>
            {basis !== 'standard' ? (
              <>
                <div className="field">
                  <label htmlFor="holiday-note">Reason</label>
                  <textarea
                    id="holiday-note"
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="holiday-worked-date">
                    Worked Date <span>Optional</span>
                  </label>
                  <DateInput
                    id="holiday-worked-date"
                    label="Worked Date"
                    value={workedDate}
                    onChange={setWorkedDate}
                  />
                </div>
              </>
            ) : null}
            <div className="form-actions">
              <button
                className="button button--quiet"
                type="button"
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
              <button className="button button--primary" type="button" onClick={() => void save()}>
                Save Treatment
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  )
}

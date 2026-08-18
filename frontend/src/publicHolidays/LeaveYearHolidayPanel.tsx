import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { formatDecimal } from '../system/decimal'
import { getLeaveYearHolidays, saveHolidayTreatment } from './api'
import { HolidayTreatmentDialog } from './HolidayTreatmentDialog'
import type { HolidayOccurrence, HolidayTreatmentInput, LeaveYearHolidays } from './types'
import './publicHolidays.css'

type Props = { consultantId: number; leaveYearId: number }

export function LeaveYearHolidayPanel({ consultantId, leaveYearId }: Props) {
  const [data, setData] = useState<LeaveYearHolidays | null>(null)
  const [editing, setEditing] = useState<HolidayOccurrence | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLeaveYearHolidays(consultantId, leaveYearId)
      .then(setData)
      .catch((e: unknown) => setError(operatorErrorMessage(e)))
  }, [consultantId, leaveYearId])

  function edit(item: HolidayOccurrence) {
    setEditing(item)
  }

  async function save(item: HolidayOccurrence, details: HolidayTreatmentInput) {
    setData(await saveHolidayTreatment(consultantId, leaveYearId, item.holiday_date, details))
    setError(null)
  }

  return (
    <section className="entitlement-holidays" aria-label="Public Holidays">
      {error ? <p className="form-notice form-notice--error">{error}</p> : null}
      {data ? (
        <details className="holiday-disclosure">
          <summary>Public Holidays ({data.occurrences.length})</summary>
          <div className="holiday-disclosure-summary">
            <span>
              Entitlement <strong>{formatDecimal(data.entitlement_hours, 1)}</strong>
            </span>
            <span>
              Standard Deductions <strong>{formatDecimal(data.deduction_hours, 1)}</strong>
            </span>
            <small>
              {data.source.replaceAll('_', ' ')} / {data.source_date}
            </small>
          </div>
          <ul>
            {data.occurrences.map((item) => (
              <li key={item.holiday_date}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.holiday_date}</span>
                </div>
                <div className="holiday-deduction-detail">
                  <span>
                    {formatDecimal(item.entitlement_hours, 1)} hours /{' '}
                    {item.basis.replaceAll('_', ' ')}
                  </span>
                  {Number(item.deduction_factor) < 1 ? (
                    <small>
                      {formatDecimal(item.contracted_pas, 2)} PA - Deduction factor{' '}
                      {formatDecimal(item.deduction_factor, 3)} -{' '}
                      {formatDecimal(item.dcc_deduction_hours, 2)} DCC /{' '}
                      {formatDecimal(item.spa_deduction_hours, 2)} SPA
                    </small>
                  ) : null}
                </div>
                <button className="text-button" type="button" onClick={() => edit(item)}>
                  Treatment
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {editing ? (
        <HolidayTreatmentDialog
          key={`${editing.holiday_date}-${editing.basis}`}
          occurrence={editing}
          onSave={(details) => save(editing, details)}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </section>
  )
}

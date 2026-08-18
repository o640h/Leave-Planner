import { useEffect, useState } from 'react'

import { operatorErrorMessage } from '../api/client'
import { listConsultants } from '../consultants/api'
import type { Consultant } from '../consultants/types'
import { listLeaveYears } from '../leaveYears/api'
import type { LeaveYear } from '../leaveYears/types'
import { getHolidaySettings, saveHolidayTreatment } from '../publicHolidays/api'
import { HolidayTreatmentDialog } from '../publicHolidays/HolidayTreatmentDialog'
import type { Holiday, HolidayOccurrence, HolidayTreatmentInput } from '../publicHolidays/types'
import { BookingDrawer } from './BookingDrawer'
import { getPlanning, previewBooking, removeBooking, saveBooking } from './api'
import { PlanningCalendar } from './PlanningCalendar'
import type { PlanningRow } from './PlanningCalendar'
import type { LeaveBooking, LeaveBookingInput, LeavePreview } from './types'
import './planning.css'

type ConsultantYears = { consultant: Consultant; leaveYears: LeaveYear[] }
type BookingContext = {
  row: PlanningRow
  booking: LeaveBooking | null
  initialDate: string | null
}
type HolidayContext = { row: PlanningRow; holiday: HolidayOccurrence }

function monthLabel(value: string): string {
  return new Date(`${value}-01T00:00:00`).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
  })
}

function currentMonth(): string {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
}

function moveMonth(value: string, offset: number): string {
  const [year, month] = value.split('-').map(Number)
  const moved = new Date(year, month - 1 + offset, 1)
  return `${moved.getFullYear()}-${String(moved.getMonth() + 1).padStart(2, '0')}`
}

function monthBounds(month: string): [string, string] {
  const [year, monthNumber] = month.split('-').map(Number)
  const lastDay = new Date(year, monthNumber, 0).getDate()
  return [`${month}-01`, `${month}-${String(lastDay).padStart(2, '0')}`]
}

export function PlanningPage() {
  const [catalogue, setCatalogue] = useState<ConsultantYears[]>([])
  const [rows, setRows] = useState<PlanningRow[]>([])
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [month, setMonth] = useState(currentMonth)
  const [context, setContext] = useState<BookingContext | null>(null)
  const [holidayContext, setHolidayContext] = useState<HolidayContext | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function loadCatalogue() {
      try {
        const [consultants, holidaySettings] = await Promise.all([
          listConsultants(),
          getHolidaySettings(),
        ])
        const result = await Promise.all(
          consultants.map(async (consultant) => ({
            consultant,
            leaveYears: await listLeaveYears(consultant.id),
          })),
        )
        if (!active) return
        setCatalogue(result)
        setHolidays(holidaySettings.holidays)
        setLoading(result.length > 0)
      } catch (caught) {
        if (active) {
          setError(operatorErrorMessage(caught))
          setLoading(false)
        }
      }
    }
    void loadCatalogue()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!month || catalogue.length === 0) return
    let active = true
    const [monthStart, monthEnd] = monthBounds(month)

    void Promise.all(
      catalogue.map(async ({ consultant, leaveYears }): Promise<PlanningRow> => {
        const leaveYear =
          leaveYears.find(
            (candidate) => candidate.start_date <= monthEnd && candidate.end_date >= monthStart,
          ) ?? null
        if (!leaveYear) return { consultant, leaveYear: null, workspace: null }
        try {
          return {
            consultant,
            leaveYear,
            workspace: await getPlanning(consultant.id, leaveYear.id),
          }
        } catch (caught) {
          return {
            consultant,
            leaveYear,
            workspace: null,
            error: operatorErrorMessage(caught),
          }
        }
      }),
    ).then((result) => {
      if (!active) return
      setRows(result)
      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [catalogue, month])

  function openNew(row: PlanningRow, date: string) {
    setHolidayContext(null)
    setContext({ row, booking: null, initialDate: date })
  }

  function openBooking(row: PlanningRow, booking: LeaveBooking) {
    setHolidayContext(null)
    setContext({ row, booking, initialDate: null })
  }

  function openHoliday(row: PlanningRow, holiday: HolidayOccurrence) {
    setContext(null)
    setHolidayContext({ row, holiday })
  }

  async function handlePreview(
    details: LeaveBookingInput,
    bookingId?: number,
  ): Promise<LeavePreview> {
    if (!context?.row.leaveYear) throw new Error('No leave year covers this date.')
    return previewBooking(context.row.consultant.id, context.row.leaveYear.id, details, bookingId)
  }

  function replaceWorkspace(consultantId: number, workspace: PlanningRow['workspace']) {
    setRows((current) =>
      current.map((row) => (row.consultant.id === consultantId ? { ...row, workspace } : row)),
    )
  }

  async function handleSave(details: LeaveBookingInput, bookingId?: number) {
    if (!context?.row.leaveYear) return
    setBusy(true)
    try {
      replaceWorkspace(
        context.row.consultant.id,
        await saveBooking(context.row.consultant.id, context.row.leaveYear.id, details, bookingId),
      )
      setContext(null)
    } finally {
      setBusy(false)
    }
  }

  async function handleRemove(bookingId: number) {
    if (!context?.row.leaveYear) return
    setBusy(true)
    try {
      replaceWorkspace(
        context.row.consultant.id,
        await removeBooking(context.row.consultant.id, context.row.leaveYear.id, bookingId),
      )
      setContext(null)
    } finally {
      setBusy(false)
    }
  }

  async function handleHolidaySave(details: HolidayTreatmentInput) {
    const leaveYear = holidayContext?.row.leaveYear
    if (!holidayContext || !leaveYear) return
    const { row, holiday } = holidayContext
    await saveHolidayTreatment(row.consultant.id, leaveYear.id, holiday.holiday_date, details)
    replaceWorkspace(row.consultant.id, await getPlanning(row.consultant.id, leaveYear.id))
  }

  return (
    <section className="planning-page" aria-labelledby="planning-title">
      <header className="planning-toolbar">
        <div>
          <span className="section-kicker">Team Calendar</span>
          <h2 id="planning-title">Planning</h2>
        </div>
        {month && (
          <div className="planning-month">
            <button
              type="button"
              aria-label="Previous Month"
              onClick={() => {
                setLoading(true)
                setError(null)
                setMonth(moveMonth(month, -1))
              }}
            >
              &lt;
            </button>
            <h3>{monthLabel(month)}</h3>
            <button
              type="button"
              aria-label="Next Month"
              onClick={() => {
                setLoading(true)
                setError(null)
                setMonth(moveMonth(month, 1))
              }}
            >
              &gt;
            </button>
          </div>
        )}
        <div className="calendar-legend" aria-label="Calendar legend">
          <span className="legend-planned">Planned</span>
          <span className="legend-approved">Approved</span>
          <span className="legend-taken">Taken</span>
          <span className="legend-holiday">Public Holiday</span>
        </div>
      </header>

      {error ? (
        <div className="planning-empty form-notice form-notice--error">{error}</div>
      ) : !month || catalogue.length === 0 ? (
        <div className="planning-empty">
          {loading ? 'Loading planning calendar...' : 'No consultants have been configured.'}
        </div>
      ) : (
        <section className="calendar-panel" aria-busy={loading}>
          {loading && <div className="wallchart-loading">Updating...</div>}
          <PlanningCalendar
            month={month}
            rows={rows}
            holidays={holidays}
            onSelectDate={openNew}
            onSelectBooking={openBooking}
            onSelectHoliday={openHoliday}
          />
        </section>
      )}

      {context?.row.leaveYear && (
        <BookingDrawer
          key={context.booking?.id ?? `new-${context.initialDate ?? ''}`}
          consultantName={context.row.consultant.name}
          booking={context.booking}
          initialDate={context.initialDate}
          busy={busy}
          onPreview={handlePreview}
          onSave={handleSave}
          onRemoveBooking={handleRemove}
          onClose={() => setContext(null)}
        />
      )}
      {holidayContext?.row.leaveYear ? (
        <HolidayTreatmentDialog
          key={`${holidayContext.row.consultant.id}-${holidayContext.holiday.holiday_date}-${holidayContext.holiday.basis}`}
          occurrence={holidayContext.holiday}
          onSave={handleHolidaySave}
          onClose={() => setHolidayContext(null)}
        />
      ) : null}
    </section>
  )
}

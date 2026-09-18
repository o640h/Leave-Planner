import type { CSSProperties } from 'react'

import type { Consultant } from '../consultants/types'
import type { LeaveYear } from '../leaveYears/types'
import type { Holiday, HolidayOccurrence } from '../publicHolidays/types'
import type { LeaveBooking, PlanningWorkspace } from './types'

export type PlanningRow = {
  consultant: Consultant
  leaveYear: LeaveYear | null
  workspace: PlanningWorkspace | null
  error?: string
}

type Props = {
  month: string
  rows: PlanningRow[]
  holidays: Holiday[]
  onSelectDate: (row: PlanningRow, date: string) => void
  onSelectBooking: (row: PlanningRow, booking: LeaveBooking) => void
  onSelectHoliday: (row: PlanningRow, holiday: HolidayOccurrence) => void
}

const stateLetter = { requested: 'R', approved: 'A', cancelled: 'C' }

function isoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function roundedHours(value?: string): string {
  return value === undefined ? '---' : String(Math.round(Number(value)))
}

function titleCase(value: string): string {
  return value.replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
}

export function PlanningCalendar({
  month,
  rows,
  holidays,
  onSelectDate,
  onSelectBooking,
  onSelectHoliday,
}: Props) {
  const [year, monthNumber] = month.split('-').map(Number)
  const days = Array.from(
    { length: new Date(year, monthNumber, 0).getDate() },
    (_, index) => index + 1,
  )
  const fixedColumnWidth = 210 + 106
  const minimumDayWidth = 28
  const gridStyle = {
    '--calendar-days': days.length,
    '--wallchart-min-width': `${fixedColumnWidth + days.length * minimumDayWidth}px`,
  } as CSSProperties

  return (
    <div className="wallchart-scroll">
      <div className="wallchart" role="grid" style={gridStyle}>
        <div className="wallchart-row wallchart-row--header" role="row">
          <span className="wallchart-name" role="columnheader">
            Consultant
          </span>
          <span className="wallchart-balance" role="columnheader">
            Remaining
          </span>
          {days.map((day) => {
            const value = new Date(year, monthNumber - 1, day)
            const weekend = value.getDay() === 0 || value.getDay() === 6
            return (
              <span
                className={`wallchart-day-heading${weekend ? ' wallchart-day--weekend' : ''}`}
                role="columnheader"
                key={day}
              >
                <small>{value.toLocaleDateString('en-GB', { weekday: 'narrow' })}</small>
                {day}
              </span>
            )
          })}
        </div>

        {rows.map((row) => {
          const balance = row.workspace?.requested?.remaining
          return (
            <div className="wallchart-row" role="row" key={row.consultant.id}>
              <span className="wallchart-name" role="rowheader">
                <strong>{row.consultant.name}</strong>
                <small>{row.consultant.post_title || 'Consultant'}</small>
              </span>
              <span className="wallchart-balance" role="gridcell">
                {balance ? (
                  <>
                    <strong>{roundedHours(balance.total_hours)}h</strong>
                    <small>
                      DCC {roundedHours(balance.dcc_hours)} / SPA {roundedHours(balance.spa_hours)}
                    </small>
                  </>
                ) : (
                  <strong className="wallchart-balance-empty">---</strong>
                )}
              </span>
              {days.map((day) => {
                const date = isoDate(year, monthNumber, day)
                const dateValue = new Date(year, monthNumber - 1, day)
                const weekend = dateValue.getDay() === 0 || dateValue.getDay() === 6
                const holiday = holidays.find((item) => item.holiday_date === date)
                const holidayOccurrence = row.workspace?.holidays.find(
                  (item) => item.holiday_date === date,
                )
                const bookings = row.workspace?.bookings.filter(
                  (booking) => booking.start_date <= date && booking.end_date >= date,
                )
                const booking =
                  bookings?.find((item) => item.state !== 'cancelled') ?? bookings?.[0]
                const unavailable =
                  !row.leaveYear ||
                  !row.workspace ||
                  date < row.leaveYear.start_date ||
                  date > row.leaveYear.end_date ||
                  Boolean(holiday && !holidayOccurrence)
                const retainedHoliday = holidayOccurrence?.basis === 'qualifying_on_call'
                const className = [
                  'wallchart-cell',
                  weekend && 'wallchart-day--weekend',
                  holiday && 'wallchart-cell--holiday',
                  retainedHoliday && 'wallchart-cell--holiday-retained',
                  !holiday && booking && `wallchart-cell--${booking.state}`,
                ]
                  .filter(Boolean)
                  .join(' ')
                const holidayName = holiday ? titleCase(holiday.name) : null
                const label = holidayName
                  ? `${row.consultant.name}, ${date}, ${holidayName}${retainedHoliday ? ', Qualifying On Call' : ''}`
                  : booking
                    ? `${row.consultant.name}, ${date}, ${titleCase(booking.state)} Leave`
                    : `${row.consultant.name}, ${date}`

                return (
                  <button
                    className={className}
                    type="button"
                    role="gridcell"
                    aria-label={label}
                    title={
                      retainedHoliday
                        ? `${holidayName} - Qualifying On Call`
                        : (holidayName ??
                          (booking ? `${titleCase(booking.state)} Leave` : 'Book Leave'))
                    }
                    disabled={unavailable}
                    key={date}
                    onClick={() =>
                      holidayOccurrence
                        ? onSelectHoliday(row, holidayOccurrence)
                        : booking
                          ? onSelectBooking(row, booking)
                          : onSelectDate(row, date)
                    }
                  >
                    {holiday ? 'PH' : booking ? stateLetter[booking.state] : ''}
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

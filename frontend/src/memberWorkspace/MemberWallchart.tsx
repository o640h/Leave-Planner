import { useEffect, useState, type CSSProperties } from 'react'

import { operatorErrorMessage } from '../api/client'
import { AppIcon } from '../system/AppIcon'
import { LivePointerLayer } from '../system/LivePointerLayer'
import { useWorkspacePointers } from '../system/workspacePointers'
import { useWorkspaceInvalidation } from '../system/workspaceInvalidation'
import { getMemberWallchart } from './api'
import type { MemberWallchart as MemberWallchartData } from './types'

function currentMonth(): string {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
}

function moveMonth(value: string, offset: number): string {
  const [year, month] = value.split('-').map(Number)
  const next = new Date(year, month - 1 + offset, 1)
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
}

function isoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

type MemberWallchartProps = {
  initialData?: MemberWallchartData
  memberName?: string | null
  onRequestDate?: (date: string) => void
}

export function MemberWallchart({
  initialData,
  memberName,
  onRequestDate,
}: MemberWallchartProps = {}) {
  const [month, setMonth] = useState(() => initialData?.month.slice(0, 7) ?? currentMonth())
  const [data, setData] = useState<MemberWallchartData | null>(initialData ?? null)
  const [error, setError] = useState<string | null>(null)
  const [reloadRevision, setReloadRevision] = useState(0)
  const pointerView = `planning:${month}`
  const { pointers, onPointerMove, onPointerLeave } = useWorkspacePointers(pointerView)

  useWorkspaceInvalidation(['planning', 'holidays', 'consultants'], () => {
    setReloadRevision((revision) => revision + 1)
  })

  useEffect(() => {
    if (initialData && month === initialData.month.slice(0, 7)) return
    let active = true
    getMemberWallchart(month)
      .then((result) => {
        if (active) setData(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(operatorErrorMessage(reason))
      })
    return () => {
      active = false
    }
  }, [initialData, month, reloadRevision])

  function changeMonth(offset: number) {
    setData(null)
    setError(null)
    setMonth((value) => moveMonth(value, offset))
  }

  const [year, monthNumber] = month.split('-').map(Number)
  const days = Array.from(
    { length: new Date(year, monthNumber, 0).getDate() },
    (_, index) => index + 1,
  )
  const monthLabel = new Date(year, monthNumber - 1, 1).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
  })
  const gridStyle = {
    '--member-calendar-days': days.length,
    '--member-wallchart-min-width': `${220 + days.length * 29}px`,
  } as CSSProperties

  return (
    <section className="member-planning" aria-labelledby="member-planning-title">
      <header className="member-planning-toolbar">
        <div>
          <span className="section-kicker">Shared Availability</span>
          <h2 id="member-planning-title">Team Wallchart</h2>
        </div>
        <div className="planning-month">
          <button type="button" aria-label="Previous Month" onClick={() => changeMonth(-1)}>
            <AppIcon name="chevronLeft" />
          </button>
          <h3>{monthLabel}</h3>
          <button type="button" aria-label="Next Month" onClick={() => changeMonth(1)}>
            <AppIcon name="chevronRight" />
          </button>
        </div>
        <div className="member-wallchart-legend">
          <span className="member-legend-requested">Requested</span>
          <span className="member-legend-approved">Approved</span>
          <span className="member-legend-holiday">Public Holiday</span>
        </div>
      </header>
      {error ? <p className="form-notice form-notice--error">{error}</p> : null}
      <div className="calendar-panel member-calendar-panel">
        {!data ? (
          <p className="wallchart-loading">Loading wallchart...</p>
        ) : (
          <div className="wallchart-scroll">
            <div
              className="member-wallchart"
              style={gridStyle}
              role="grid"
              aria-label={`Team availability for ${monthLabel}`}
              onPointerMove={onPointerMove}
              onPointerLeave={onPointerLeave}
            >
              <div className="member-wallchart-row member-wallchart-row--header" role="row">
                <div className="member-wallchart-name" role="columnheader">
                  Consultant
                </div>
                {days.map((day) => {
                  const value = new Date(year, monthNumber - 1, day)
                  return (
                    <div
                      className={`member-wallchart-day${value.getDay() === 0 || value.getDay() === 6 ? ' member-wallchart-day--weekend' : ''}`}
                      role="columnheader"
                      key={day}
                    >
                      <small>
                        {value.toLocaleDateString('en-GB', { weekday: 'short' }).slice(0, 1)}
                      </small>
                      {day}
                    </div>
                  )
                })}
              </div>
              {data.people.map((person) => {
                const isMember = person.display_name === memberName
                const leaveByDate = new Map(
                  person.leave_dates.map((entry) => [entry.leave_date, entry.state]),
                )
                return (
                  <div className="member-wallchart-row" role="row" key={person.display_name}>
                    <div className="member-wallchart-name" role="rowheader">
                      <strong>{person.display_name}</strong>
                    </div>
                    {days.map((day) => {
                      const date = isoDate(year, monthNumber, day)
                      const dateValue = new Date(year, monthNumber - 1, day)
                      const holiday = data.holidays.find((item) => item.holiday_date === date)
                      const leaveState = holiday ? undefined : leaveByDate.get(date)
                      const stateLabel = leaveState
                        ? leaveState[0].toUpperCase() + leaveState.slice(1)
                        : null
                      const label = holiday
                        ? `${person.display_name}, ${date}, ${holiday.name}`
                        : stateLabel
                          ? `${person.display_name}, ${date}, ${stateLabel}`
                          : `${person.display_name}, ${date}`
                      const className = [
                        'member-wallchart-cell',
                        leaveState ? `member-wallchart-cell--${leaveState}` : '',
                        holiday ? 'member-wallchart-cell--holiday' : '',
                        dateValue.getDay() === 0 || dateValue.getDay() === 6
                          ? 'member-wallchart-day--weekend'
                          : '',
                        isMember && !leaveState && !holiday
                          ? 'member-wallchart-cell--requestable'
                          : '',
                      ]
                        .filter(Boolean)
                        .join(' ')
                      return isMember && !leaveState && !holiday && onRequestDate ? (
                        <button
                          className={className}
                          type="button"
                          aria-label={`${label}, Request Leave`}
                          title="Request Leave"
                          key={date}
                          onClick={() => onRequestDate(date)}
                        />
                      ) : (
                        <div
                          className={[className].join(' ')}
                          role="gridcell"
                          aria-label={label}
                          title={holiday?.name ?? stateLabel ?? undefined}
                          key={date}
                        />
                      )
                    })}
                  </div>
                )
              })}
              <LivePointerLayer pointers={pointers} />
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

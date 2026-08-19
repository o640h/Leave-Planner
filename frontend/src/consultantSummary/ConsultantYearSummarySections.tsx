import { useState } from 'react'

import { formatDecimal } from '../system/decimal'
import type {
  AuditEvent,
  BalancePosition,
  ConsultantYearSummary,
  JobPlanPeriodSummary,
} from './types'
import { LeaveLog } from './LeaveLog'
import './consultantSummary.css'

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})
const dateTimeFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function hours(value: string, precision = 2): string {
  return `${formatDecimal(value, precision)}h`
}

function BalancePositionView({ position }: { position: BalancePosition | null }) {
  if (!position) return <p className="summary-empty">Apply entitlement to calculate balances.</p>
  return (
    <div className="balance-position">
      <div>
        <span>Available</span>
        <strong>{hours(position.available.total_hours, 0)}</strong>
        <small>
          DCC {formatDecimal(position.available.dcc_hours, 0)} / SPA{' '}
          {formatDecimal(position.available.spa_hours, 0)}
        </small>
      </div>
      <div>
        <span>Leave Taken</span>
        <strong>{hours(position.used.total_hours, 0)}</strong>
        <small>
          DCC {formatDecimal(position.used.dcc_hours, 0)} / SPA{' '}
          {formatDecimal(position.used.spa_hours, 0)}
        </small>
      </div>
      <div>
        <span>Leave Remaining</span>
        <strong>{hours(position.remaining.total_hours, 0)}</strong>
        <small>
          DCC {formatDecimal(position.remaining.dcc_hours, 0)} / SPA{' '}
          {formatDecimal(position.remaining.spa_hours, 0)}
        </small>
      </div>
    </div>
  )
}

export function LeaveBalanceSummary({ summary }: { summary: ConsultantYearSummary | null }) {
  const [view, setView] = useState<'actual' | 'confirmed' | 'projected'>('actual')
  if (!summary) return <p className="summary-empty">Loading leave position...</p>

  return (
    <section className="leave-position" aria-labelledby="leave-position-title">
      <header>
        <h5 id="leave-position-title">Leave Position</h5>
        <div className="balance-tabs" role="group" aria-label="Balance View">
          {(['actual', 'confirmed', 'projected'] as const).map((item) => (
            <button
              type="button"
              className={view === item ? 'balance-tab balance-tab--active' : 'balance-tab'}
              key={item}
              onClick={() => setView(item)}
            >
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>
      </header>
      <BalancePositionView position={summary.balances[view]} />
      <div className="weekday-counts" aria-label="Logged Leave Dates by Weekday">
        {Object.entries(summary.weekday_counts).map(([weekday, count]) => (
          <div key={weekday}>
            <span>{weekday.slice(0, 3)}</span>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
    </section>
  )
}

function PeriodRow({ period, index }: { period: JobPlanPeriodSummary; index: number }) {
  return (
    <div className="period-row" role="row">
      <div role="cell">
        <strong>Job Plan {index + 1}</strong>
        <span>
          {formatDate(period.effective_from)} - {formatDate(period.effective_until)}
        </span>
      </div>
      <div role="cell">
        <span>Calendar Days</span>
        <strong>{period.calendar_days}</strong>
      </div>
      <div role="cell">
        <span>PA Split</span>
        <strong>
          {formatDecimal(period.dcc_pas)} DCC / {formatDecimal(period.spa_pas)} SPA
        </strong>
      </div>
      <div role="cell">
        <span>Standard Week</span>
        <strong>
          {formatDecimal(period.standard_dcc_hours, 2)} DCC /{' '}
          {formatDecimal(period.standard_spa_hours, 2)} SPA
        </strong>
      </div>
      <div role="cell">
        <span>Leave Calculated</span>
        <strong>{hours(period.gross_entitlement_hours, 1)}</strong>
        <small>
          DCC {formatDecimal(period.dcc_entitlement_hours, 1)} / SPA{' '}
          {formatDecimal(period.spa_entitlement_hours, 1)}
        </small>
      </div>
    </div>
  )
}

function auditLabel(event: AuditEvent): string {
  const subject = event.entity_type
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
  return `${subject} ${event.action}`
}

export function ConsultantYearSummarySections({ summary }: { summary: ConsultantYearSummary }) {
  const warnings = summary.warnings.filter(
    (warning) => warning.code !== 'leave-balance.carry-forward',
  )
  return (
    <>
      <details className="dashboard-panel summary-panel summary-panel--periods">
        <summary>
          <span>Annual Leave by Job Plan</span>
          <small>
            {summary.job_plan_periods.length}{' '}
            {summary.job_plan_periods.length === 1 ? 'Period' : 'Periods'} /{' '}
            {summary.allocation_source === 'recommendation' ? 'Calculated Total' : 'Applied Total'}
          </small>
        </summary>
        {summary.job_plan_periods.length ? (
          <div className="period-table" role="table" aria-label="Annual Leave by Job Plan">
            {summary.job_plan_periods.map((period, index) => (
              <PeriodRow key={period.job_plan_id} period={period} index={index} />
            ))}
          </div>
        ) : (
          <p className="summary-empty">Add a job plan to calculate the leave-year periods.</p>
        )}
      </details>

      {warnings.length ? (
        <section className="summary-warnings" aria-labelledby="summary-warnings-title">
          <h4 id="summary-warnings-title">Needs Attention</h4>
          {warnings.map((warning) => (
            <p key={warning.code}>{warning.message}</p>
          ))}
        </section>
      ) : null}

      <LeaveLog summary={summary} />

      <details className="dashboard-panel summary-audit">
        <summary>
          <span>Recent Changes</span>
          <small>{summary.audit_events.length} Events</small>
        </summary>
        <div>
          {summary.audit_events.map((event) => (
            <p key={event.id}>
              <strong>{auditLabel(event)}</strong>
              <time dateTime={event.recorded_at}>
                {event.actor_label} · {dateTimeFormatter.format(new Date(event.recorded_at))}
              </time>
            </p>
          ))}
        </div>
      </details>
    </>
  )
}

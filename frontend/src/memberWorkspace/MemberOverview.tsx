import { useState } from 'react'

import { AppIcon } from '../system/AppIcon'
import { addNonNegativeDecimals, formatDecimal } from '../system/decimal'
import type {
  MemberBalancePosition,
  MemberJobPlan,
  MemberWorkspaceData,
  MemberYearSummary,
} from './types'

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})
const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function formatDate(value: string | null): string {
  if (!value) return 'Full Leave Year'
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function hours(value: string, precision = 2): string {
  return `${formatDecimal(value, precision)}h`
}

function BalancePosition({
  position,
  view,
}: {
  position: MemberBalancePosition | null
  view: 'requested' | 'approved'
}) {
  if (!position) {
    return <p className="member-empty">Entitlement has not been applied for this leave year.</p>
  }
  return (
    <div className="member-balance-grid">
      {[
        ['Available', position.available],
        [view === 'requested' ? 'Leave Requested' : 'Leave Approved', position.used],
        ['Remaining', position.remaining],
      ].map(([label, amounts]) => {
        const value = amounts as typeof position.available
        return (
          <div key={label as string}>
            <span>{label as string}</span>
            <strong>{hours(value.total_hours)}</strong>
            <small>
              DCC {formatDecimal(value.dcc_hours, 2)} / SPA {formatDecimal(value.spa_hours, 2)}
            </small>
          </div>
        )
      })}
    </div>
  )
}

function JobPlanPattern({ plan }: { plan: MemberJobPlan }) {
  return (
    <details className="member-job-plan">
      <summary>
        <span>
          <strong>
            {formatDate(plan.effective_from)} - {formatDate(plan.effective_until)}
          </strong>
          <small>
            {formatDecimal(plan.contracted_pas)} PA · {formatDecimal(plan.dcc_pas)} DCC /{' '}
            {formatDecimal(plan.spa_pas)} SPA · {plan.week_count}{' '}
            {plan.week_count === 1 ? 'Week' : 'Weeks'}
          </small>
        </span>
        <span>View Pattern</span>
      </summary>
      <div className="member-pattern-table">
        <div className="member-pattern-heading">Week</div>
        <div className="member-pattern-heading">Day</div>
        <div className="member-pattern-heading">DCC</div>
        <div className="member-pattern-heading">SPA</div>
        {plan.days.map((day) => (
          <div className="member-pattern-row" key={`${day.cycle_week}-${day.weekday}`}>
            <span>{day.cycle_week}</span>
            <strong>{weekdays[day.weekday]}</strong>
            <span>{hours(day.dcc_hours)}</span>
            <span>{hours(day.spa_hours)}</span>
          </div>
        ))}
      </div>
    </details>
  )
}

type MemberOverviewProps = {
  data: MemberWorkspaceData
  loadingYear: boolean
  onLeaveYearSelected: (leaveYearId: number) => void
}

export function MemberOverview({ data, loadingYear, onLeaveYearSelected }: MemberOverviewProps) {
  const [balanceView, setBalanceView] = useState<'requested' | 'approved'>('approved')
  const summary = data.selected_year
  if (!data.consultant) return null

  function bookingHours(days: MemberYearSummary['bookings'][number]['days']): string {
    return days.reduce(
      (total, day) => addNonNegativeDecimals(total, day.deduction.total_hours),
      '0',
    )
  }

  return (
    <section className="member-overview" aria-labelledby="member-overview-title">
      <header className="member-overview-header">
        <div className="member-identity">
          <span className="member-monogram" aria-hidden="true">
            {data.consultant.name
              .split(/\s+/)
              .slice(0, 2)
              .map((part) => part[0])
              .join('')}
          </span>
          <div>
            <span className="section-kicker">My Consultant Workspace</span>
            <h2 id="member-overview-title">{data.consultant.name}</h2>
            <p>{data.consultant.post_title ?? 'Post Title Not Set'}</p>
          </div>
        </div>
        {data.leave_years.length > 1 ? (
          <label className="member-year-select">
            <span>Leave Year</span>
            <select
              value={summary?.leave_year.id ?? ''}
              disabled={loadingYear}
              onChange={(event) => onLeaveYearSelected(Number(event.target.value))}
            >
              {data.leave_years.map((year) => (
                <option key={year.id} value={year.id}>
                  {formatDate(year.start_date)} - {formatDate(year.end_date)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </header>

      {loadingYear ? (
        <p className="member-loading" role="status">
          Loading leave year...
        </p>
      ) : null}
      {!summary ? (
        <div className="member-zero-state">
          <AppIcon name="calendar" />
          <h3>No Leave Year Available</h3>
          <p>Your workspace operator has not configured a leave year for this record.</p>
        </div>
      ) : (
        <div className="member-dashboard">
          <section className="dashboard-panel member-balance-panel">
            <header className="member-panel-heading member-panel-heading--tabs">
              <h3>Leave Position</h3>
              <div className="balance-tabs" role="group" aria-label="Balance View">
                {(['requested', 'approved'] as const).map((view) => (
                  <button
                    className={
                      balanceView === view ? 'balance-tab balance-tab--active' : 'balance-tab'
                    }
                    type="button"
                    key={view}
                    onClick={() => setBalanceView(view)}
                  >
                    {view[0].toUpperCase() + view.slice(1)}
                  </button>
                ))}
              </div>
            </header>
            <BalancePosition position={summary.balances[balanceView]} view={balanceView} />
            <div className="weekday-counts">
              {Object.entries(summary.weekday_counts).map(([weekday, count]) => (
                <div key={weekday}>
                  <span>{weekday.slice(0, 3)}</span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="dashboard-panel member-year-panel">
            <header className="member-panel-heading">
              <div>
                <span className="section-kicker">Current Period</span>
                <h3>Leave Year</h3>
              </div>
              <span className="member-read-only">Read Only</span>
            </header>
            <dl className="member-definition-grid">
              <div>
                <dt>Starts</dt>
                <dd>{formatDate(summary.leave_year.start_date)}</dd>
              </div>
              <div>
                <dt>Ends</dt>
                <dd>{formatDate(summary.leave_year.end_date)}</dd>
              </div>
              <div>
                <dt>Employment Starts</dt>
                <dd>{formatDate(summary.leave_year.employment_start)}</dd>
              </div>
              <div>
                <dt>Employment Ends</dt>
                <dd>{formatDate(summary.leave_year.employment_end)}</dd>
              </div>
            </dl>
          </section>

          <section className="dashboard-panel member-entitlement-panel">
            <header className="member-panel-heading">
              <div>
                <span className="section-kicker">Opening Allowance</span>
                <h3>Annual Entitlement</h3>
              </div>
              <span className="member-read-only">
                {summary.entitlement.application?.mode === 'manual'
                  ? 'Manually Applied'
                  : 'Calculated'}
              </span>
            </header>
            {summary.entitlement.application ? (
              <>
                <div className="member-entitlement-totals">
                  <div>
                    <span>Applied Total</span>
                    <strong>
                      {hours(summary.entitlement.application.entitlement.total_hours, 3)}
                    </strong>
                  </div>
                  <div>
                    <span>DCC</span>
                    <strong>
                      {hours(summary.entitlement.application.entitlement.dcc_hours, 3)}
                    </strong>
                  </div>
                  <div>
                    <span>SPA</span>
                    <strong>
                      {hours(summary.entitlement.application.entitlement.spa_hours, 3)}
                    </strong>
                  </div>
                  <div>
                    <span>Carry Forward</span>
                    <strong>{hours(summary.carry_forward.total_hours)}</strong>
                  </div>
                </div>
                {summary.entitlement.application.reason ? (
                  <p className="member-application-reason">
                    {summary.entitlement.application.reason}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="member-empty">No annual entitlement has been applied.</p>
            )}
            {summary.entitlement.recommendation ? (
              <details className="member-calculation-details">
                <summary>How This Was Calculated</summary>
                <div className="member-components">
                  {summary.entitlement.recommendation.components.map((component) => (
                    <div key={`${component.kind}-${component.label}`}>
                      <span>{component.label}</span>
                      <strong>{hours(component.prorated_hours, 3)}</strong>
                    </div>
                  ))}
                </div>
                <ol>
                  {summary.entitlement.recommendation.trace.map((step, index) => (
                    <li key={`${step.description}-${index}`}>
                      <span>{step.description}</span>
                      {step.amount ? <strong>{hours(step.amount, 3)}</strong> : null}
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}
          </section>

          <section className="dashboard-panel member-job-plans-panel">
            <header className="member-panel-heading">
              <div>
                <span className="section-kicker">Effective Patterns</span>
                <h3>Job Plans</h3>
              </div>
              <span>
                {summary.job_plans.length} {summary.job_plans.length === 1 ? 'Plan' : 'Plans'}
              </span>
            </header>
            {summary.job_plans.length ? (
              summary.job_plans.map((plan, index) => (
                <JobPlanPattern plan={plan} key={`${plan.effective_from}-${index}`} />
              ))
            ) : (
              <p className="member-empty">No job plan has been configured.</p>
            )}
          </section>

          <section className="dashboard-panel member-bookings-panel">
            <header className="member-panel-heading">
              <div>
                <span className="section-kicker">Your Records</span>
                <h3>Leave Bookings</h3>
              </div>
              <span>
                {summary.bookings.length} {summary.bookings.length === 1 ? 'Booking' : 'Bookings'}
              </span>
            </header>
            {summary.bookings.length ? (
              <div className="member-booking-list">
                {summary.bookings.map((booking, index) => (
                  <article key={`${booking.start_date}-${booking.end_date}-${index}`}>
                    <span className={`member-state member-state--${booking.state}`}>
                      {booking.state[0].toUpperCase() + booking.state.slice(1)}
                    </span>
                    <div>
                      <strong>
                        {formatDate(booking.start_date)} - {formatDate(booking.end_date)}
                      </strong>
                      {booking.note ? <small>{booking.note}</small> : null}
                    </div>
                    <span>{hours(bookingHours(booking.days))}</span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="member-empty">
                No leave bookings have been recorded for this leave year.
              </p>
            )}
          </section>
        </div>
      )}
    </section>
  )
}

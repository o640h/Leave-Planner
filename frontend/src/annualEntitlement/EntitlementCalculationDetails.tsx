import { formatDecimal } from '../system/decimal'
import type { EntitlementRecommendation, EntitlementTraceStep } from './types'

type Props = {
  recommendation: EntitlementRecommendation
}

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return dateFormatter.format(new Date(year, month - 1, day))
}

function amount(value: string | null | undefined): string {
  return value ? formatDecimal(value, 3) : '0'
}

function uniqueTrace(steps: EntitlementTraceStep[]): EntitlementTraceStep[] {
  const seen = new Set<string>()

  return steps.filter((step) => {
    const key = `${step.rule_id}|${step.amount}|${JSON.stringify(step.context)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function title(step: EntitlementTraceStep): string {
  if (step.rule_id.startsWith('entitlement.era')) return 'Contract-Era Rule'
  if (step.rule_id.startsWith('entitlement.tier')) return 'Service Tier'
  if (step.rule_id === 'entitlement.pa-proration') return 'PA Pro-Rata'
  if (step.rule_id === 'leave-calculation.calendar-days') {
    return 'Base Leave for Job Plan Period'
  }
  if (step.rule_id === 'public-holiday.standard-eight-hours') {
    return step.context.holiday_name ?? 'Public Holiday'
  }
  return step.description
}

function explanation(step: EntitlementTraceStep): string {
  const context = step.context

  if (step.rule_id.startsWith('entitlement.era')) {
    return context.appointment_era ?? step.description
  }
  if (step.rule_id.startsWith('entitlement.tier')) {
    return `Full-time entitlement at this tier: ${amount(step.amount)} hours.`
  }
  if (step.rule_id === 'entitlement.pa-proration') {
    return `${amount(context.full_time_hours)} hours × ${amount(context.capped_pas)} PA ÷ ${amount(
      context.pa_cap,
    )} PA = ${amount(step.amount)} hours.`
  }
  if (step.rule_id === 'leave-calculation.calendar-days') {
    return `${amount(context.full_year_hours)} base hours × ${context.calendar_days} days ÷ ${
      context.leave_year_days
    } leave-year days = ${amount(step.amount)} hours.`
  }
  if (step.rule_id === 'public-holiday.standard-eight-hours') {
    return `8 hours × ${amount(context.pa_factor)} PA factor = ${amount(step.amount)} hours.`
  }
  return step.description
}

function metadata(step: EntitlementTraceStep): string | null {
  const context = step.context

  if (step.rule_id === 'leave-calculation.calendar-days') {
    return `${formatDate(context.period_start)} – ${formatDate(context.period_end)} · DCC ${amount(
      context.dcc_hours,
    )} · SPA ${amount(context.spa_hours)}`
  }
  if (step.rule_id === 'public-holiday.standard-eight-hours' && step.effective_date) {
    return `${formatDate(step.effective_date)} · DCC ${amount(
      context.dcc_entitlement_hours,
    )} · SPA ${amount(context.spa_entitlement_hours)}`
  }
  if (step.rule_id.startsWith('entitlement.tier')) {
    return `Tier begins at ${context.minimum_completed_years ?? '0'} completed service years.`
  }
  return null
}

export function EntitlementCalculationDetails({ recommendation }: Props) {
  const { inputs } = recommendation

  return (
    <details className="entitlement-trace">
      <summary>How This Was Calculated</summary>

      <div className="entitlement-calculation-basis">
        <p>
          The policy tier combines Basic Leave, Statutory Days, any earned Seniority, and Hospital
          R&amp;R. That full-time total is pro-rated by PA. Public holidays are calculated
          separately and added afterwards.
        </p>
        <p className="entitlement-total-formula">
          <strong>Recommended Total</strong>
          <span>
            {amount(recommendation.base_entitlement.total_hours)} base +{' '}
            {amount(recommendation.public_holiday_entitlement.total_hours)} public holidays ={' '}
            {amount(recommendation.recommended_entitlement.total_hours)} hours
          </span>
        </p>
        <p>
          Appointment Date selects the contract-era rule. Reckonable Service Start determines the
          service tier. The period rows below divide base leave across each job plan by calendar
          days; they exclude the separately listed public holidays.
        </p>
        <dl>
          <div>
            <dt>Appointment Date</dt>
            <dd>{formatDate(inputs.consultant_appointment_date)}</dd>
          </div>
          <div>
            <dt>Reckonable Service Start</dt>
            <dd>{formatDate(inputs.consultant_service_start_date)}</dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>{inputs.policy_versions.join(', ')}</dd>
          </div>
          <div>
            <dt>Holiday Source</dt>
            <dd>
              {inputs.public_holiday_source.replaceAll('_', ' ')} ·{' '}
              {formatDate(inputs.public_holiday_source_date)}
            </dd>
          </div>
        </dl>
      </div>

      <ol>
        {uniqueTrace(recommendation.trace).map((step, index) => {
          const meta = metadata(step)
          return (
            <li key={`${step.rule_id}-${step.effective_date}-${index}`}>
              <div>
                <strong>{title(step)}</strong>
                <p>{explanation(step)}</p>
                {meta ? <span>{meta}</span> : null}
              </div>
            </li>
          )
        })}
      </ol>
    </details>
  )
}

import { formatDecimal } from '../system/decimal'
import type { EntitlementRecommendation, EntitlementTraceStep } from './types'

type Props = { recommendation: EntitlementRecommendation }

function traceGroup(steps: EntitlementTraceStep[], prefix: string): EntitlementTraceStep[] {
  return steps.filter((step) => step.rule_id.startsWith(prefix))
}

function value(value: string | null | undefined): string {
  return value ? formatDecimal(value, 3) : '0'
}

export function EntitlementCalculationDetails({ recommendation }: Props) {
  const policy = recommendation.trace.filter(
    (step) =>
      step.rule_id.startsWith('entitlement.era') || step.rule_id.startsWith('entitlement.tier'),
  )
  const prorata = traceGroup(recommendation.trace, 'entitlement.pa-proration')
  const periods = traceGroup(recommendation.trace, 'leave-calculation.calendar-days')

  return (
    <div className="entitlement-explanation">
      <details>
        <summary>Calculation Basis</summary>
        <div className="entitlement-basis-grid">
          <div>
            <span>Appointment Date</span>
            <strong>{recommendation.inputs.consultant_appointment_date}</strong>
          </div>
          <div>
            <span>Reckonable Service Start</span>
            <strong>{recommendation.inputs.consultant_service_start_date}</strong>
          </div>
          <div>
            <span>Policy</span>
            <strong>{recommendation.inputs.policy_versions.join(', ')}</strong>
          </div>
          <div>
            <span>Holiday Source</span>
            <strong>
              {recommendation.inputs.public_holiday_source.replaceAll('_', ' ')} /{' '}
              {recommendation.inputs.public_holiday_source_date}
            </strong>
          </div>
        </div>
        <ul className="calculation-lines">
          {policy.map((step) => (
            <li key={`${step.rule_id}-${step.effective_date}`}>
              <strong>{step.context.appointment_era ?? step.description}</strong>
              {step.amount ? <span>{value(step.amount)} full-time hours</span> : null}
            </li>
          ))}
          {prorata.map((step) => (
            <li key={`${step.rule_id}-${step.effective_date}`}>
              <strong>PA Pro-Rata</strong>
              <span>
                {value(step.context.full_time_hours)} x {value(step.context.capped_pas)} PA /{' '}
                {value(step.context.pa_cap)} PA = {value(step.amount)} hours
              </span>
            </li>
          ))}
        </ul>
      </details>
      <details>
        <summary>Job Plan Periods</summary>
        <ul className="calculation-lines">
          {periods.map((step) => (
            <li key={`${step.rule_id}-${step.effective_date}`}>
              <strong>
                {step.context.period_start} - {step.context.period_end}
              </strong>
              <span>
                {value(step.context.full_year_hours)} x {step.context.calendar_days} days /{' '}
                {step.context.leave_year_days} days = {value(step.amount)} hours
              </span>
              <small>
                DCC {value(step.context.dcc_hours)} / SPA {value(step.context.spa_hours)}
              </small>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}

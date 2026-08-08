import { NumberInput } from '../system/NumberInput'
import type { JobPlanDayInput } from './types'

const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

type HoursField = 'dcc_hours' | 'spa_hours'

type HoursTableProps = {
  cycleWeek: number
  weekdayNumbers: number[]
  days: JobPlanDayInput[]
  disabled: boolean
  onChange: (cycleWeek: number, weekday: number, field: HoursField, value: string) => void
}

function HoursTable({ cycleWeek, weekdayNumbers, days, disabled, onChange }: HoursTableProps) {
  return (
    <div className="job-plan-grid-scroll">
      <table className="job-plan-grid">
        <thead>
          <tr>
            <th scope="col">Day</th>
            <th scope="col">DCC Hours</th>
            <th scope="col">SPA Hours</th>
          </tr>
        </thead>

        <tbody>
          {weekdayNumbers.map((weekday) => {
            const day = days.find(
              (candidate) => candidate.cycle_week === cycleWeek && candidate.weekday === weekday,
            )

            if (!day) return null

            return (
              <tr key={weekday}>
                <th scope="row">{weekdays[weekday]}</th>

                {(
                  [
                    ['dcc_hours', 'DCC'],
                    ['spa_hours', 'SPA'],
                  ] as const
                ).map(([field, label]) => (
                  <td key={field}>
                    <NumberInput
                      label={`${weekdays[weekday]} ${label} Hours Week ${cycleWeek}`}
                      min="0"
                      step="0.001"
                      inputMode="decimal"
                      value={day[field]}
                      disabled={disabled}
                      onChange={(value) => onChange(cycleWeek, weekday, field, value)}
                    />
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

type JobPlanGridProps = {
  weekCount: number
  days: JobPlanDayInput[]
  disabled: boolean
  onChange: HoursTableProps['onChange']
}

export function JobPlanGrid({ weekCount, days, disabled, onChange }: JobPlanGridProps) {
  return (
    <div className="job-plan-weeks">
      {Array.from({ length: weekCount }, (_, index) => {
        const cycleWeek = index + 1

        return (
          <section className="job-plan-week" key={cycleWeek}>
            <h4>{weekCount === 1 ? 'Standard Week' : `Week ${cycleWeek}`}</h4>

            <HoursTable
              cycleWeek={cycleWeek}
              weekdayNumbers={[0, 1, 2, 3, 4]}
              days={days}
              disabled={disabled}
              onChange={onChange}
            />

            <details className="weekend-hours">
              <summary>Weekend Hours</summary>

              <HoursTable
                cycleWeek={cycleWeek}
                weekdayNumbers={[5, 6]}
                days={days}
                disabled={disabled}
                onChange={onChange}
              />
            </details>
          </section>
        )
      })}
    </div>
  )
}

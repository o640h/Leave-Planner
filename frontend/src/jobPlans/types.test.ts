import { expect, it } from 'vitest'

import { editableJobPlan, type JobPlan } from './types'

it('removes a hidden cycle anchor when editing a one-week plan', () => {
  const plan: JobPlan = {
    id: 1,
    leave_year_id: 1,
    effective_from: '2026-08-18',
    effective_until: '2027-08-13',
    cycle_anchor_date: '2026-08-17',
    week_count: 1,
    contracted_pas: '8.470',
    dcc_pas: '5.910',
    spa_pas: '2.560',
    other_pas: '0',
    hours_per_pa: '4',
    reconciliation_override_reason: null,
    days: [],
  }

  // A one-week pattern is identical every week, so an old generated anchor
  // must not prevent the operator moving the plan to an earlier date.
  expect(editableJobPlan(plan).cycle_anchor_date).toBeNull()
})

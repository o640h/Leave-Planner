import { afterEach, describe, expect, it, vi } from 'vitest'

import { createJobPlan, listJobPlans } from './api'
import type { JobPlan, JobPlanInput } from './types'

const operatorInput: JobPlanInput = {
  effective_from: '2025-08-29',
  effective_until: '2026-08-28',
  cycle_anchor_date: null,
  week_count: 1,
  contracted_pas: '8.47',
  dcc_pas: '5.91',
  spa_pas: '2.56',
  other_pas: '0',
  hours_per_pa: '4',
  reconciliation_override_reason: null,
  days: [],
}

function json(body: unknown) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) }
}

describe('job plan inclusive date boundary', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the exclusive API boundary as the preceding inclusive date', async () => {
    // The stored boundary is the first day after the operator-visible period.
    const apiRecord: JobPlan = {
      ...operatorInput,
      id: 4,
      leave_year_id: 2,
      effective_until: '2026-08-29',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json([apiRecord])))

    const records = await listJobPlans(1, 2)

    expect(records[0].effective_until).toBe('2026-08-28')
  })

  it('sends an inclusive end date as the next exclusive API boundary', async () => {
    // Keep half-open storage internal while the form and returned record remain inclusive.
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, options: RequestInit = {}) => {
      const submitted = JSON.parse(options.body as string) as JobPlanInput
      return json({ ...submitted, id: 4, leave_year_id: 2 })
    })
    vi.stubGlobal('fetch', fetchMock)

    const created = await createJobPlan(1, 2, operatorInput)
    const request = fetchMock.mock.calls[0]?.[1]
    if (!request) {
      throw new Error('Expected createJobPlan to submit a request')
    }
    const submitted = JSON.parse(request.body as string) as JobPlanInput

    expect(submitted.effective_until).toBe('2026-08-29')
    expect(created.effective_until).toBe('2026-08-28')
  })
})

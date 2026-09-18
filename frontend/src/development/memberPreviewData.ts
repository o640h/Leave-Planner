import type { MemberWallchart, MemberWorkspaceData } from '../memberWorkspace/types'
import type { PolicyDocument } from '../policies/types'

export const memberPreviewPolicyDocuments: PolicyDocument[] = [
  {
    document_id: 'hr78',
    document_type: 'Policy',
    title: 'Medical and Dental Annual Leave Policy',
    version: '3',
    effective_date: '2025-07-01',
    filename: 'HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf',
  },
  {
    document_id: 'hrs09',
    document_type: 'Guidance',
    title: 'Medical and Dental Annual Leave Guidance',
    version: '1',
    effective_date: '2025-07-01',
    filename: 'HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf',
  },
]

export const memberPreviewWallchart: MemberWallchart = {
  month: '2026-09-01',
  holidays: [],
  people: [
    {
      display_name: 'Alex Morgan',
      leave_dates: [21, 22, 23].map((day) => ({
        leave_date: `2026-09-${day}`,
        state: 'approved' as const,
      })),
    },
    {
      display_name: 'Jordan Patel',
      leave_dates: [7, 8].map((day) => ({
        leave_date: `2026-09-0${day}`,
        state: 'requested' as const,
      })),
    },
    {
      display_name: 'Sam Taylor',
      leave_dates: [28, 29, 30].map((day) => ({
        leave_date: `2026-09-${day}`,
        state: 'approved' as const,
      })),
    },
  ],
}

export const memberPreviewData: MemberWorkspaceData = {
  state: 'linked',
  workspace_name: 'Consultants',
  consultant: { name: 'Alex Morgan', post_title: 'Consultant in Radiology' },
  leave_years: [
    {
      id: 1,
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      employment_start: '2026-02-01',
      employment_end: null,
    },
  ],
  selected_year: {
    leave_year: {
      id: 1,
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      employment_start: '2026-02-01',
      employment_end: null,
    },
    job_plans: [
      {
        effective_from: '2026-01-01',
        effective_until: '2026-12-31',
        cycle_anchor_date: '2026-01-05',
        week_count: 1,
        contracted_pas: '9',
        dcc_pas: '8',
        spa_pas: '1',
        other_pas: '0',
        hours_per_pa: '4',
        days: [
          { cycle_week: 1, weekday: 0, dcc_hours: '8', spa_hours: '0', other_hours: '0' },
          { cycle_week: 1, weekday: 2, dcc_hours: '8', spa_hours: '4', other_hours: '0' },
          { cycle_week: 1, weekday: 4, dcc_hours: '8', spa_hours: '0', other_hours: '0' },
        ],
      },
    ],
    entitlement: {
      recommendation: null,
      application: {
        mode: 'calculated',
        entitlement: {
          dcc_hours: '255.632',
          spa_hours: '31.954',
          other_hours: '0',
          total_hours: '287.586',
        },
        reason: null,
        updated_at: '2026-09-18T09:00:00Z',
      },
    },
    carry_forward: { dcc_hours: '12', spa_hours: '0', total_hours: '12' },
    allocation_source: 'applied',
    job_plan_periods: [],
    holidays: [],
    bookings: [
      {
        start_date: '2026-09-21',
        end_date: '2026-09-23',
        state: 'approved',
        note: null,
        days: [
          {
            leave_date: '2026-09-21',
            deduction: {
              dcc_hours: '8',
              spa_hours: '0',
              other_hours: '0',
              total_hours: '8',
            },
            override_reason: null,
            public_holiday_name: null,
          },
          {
            leave_date: '2026-09-23',
            deduction: {
              dcc_hours: '8',
              spa_hours: '4',
              other_hours: '0',
              total_hours: '12',
            },
            override_reason: null,
            public_holiday_name: null,
          },
        ],
      },
    ],
    balances: {
      approved: {
        available: {
          dcc_hours: '263.632',
          spa_hours: '35.954',
          other_hours: '0',
          total_hours: '299.586',
        },
        used: { dcc_hours: '56', spa_hours: '12', other_hours: '0', total_hours: '68' },
        remaining: {
          dcc_hours: '207.632',
          spa_hours: '23.954',
          other_hours: '0',
          total_hours: '231.586',
        },
      },
      requested: {
        available: {
          dcc_hours: '263.632',
          spa_hours: '35.954',
          other_hours: '0',
          total_hours: '299.586',
        },
        used: { dcc_hours: '72', spa_hours: '16', other_hours: '0', total_hours: '88' },
        remaining: {
          dcc_hours: '191.632',
          spa_hours: '19.954',
          other_hours: '0',
          total_hours: '211.586',
        },
      },
    },
    weekday_counts: { monday: 5, tuesday: 0, wednesday: 3, thursday: 0, friday: 2 },
    warnings: [
      {
        code: 'carry-forward.review',
        message: 'Carry-forward requires an operator review.',
        severity: 'info',
      },
    ],
  },
}

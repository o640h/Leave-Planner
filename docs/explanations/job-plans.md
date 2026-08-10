# Job Plans

The job-plan model is intentionally much smaller than a rota system. It stores only the
information needed to reproduce and improve the supplied leave workbook:

1. the consultant's overall contracted DCC, SPA, and Other PAs;
2. the standard DCC, SPA, and Other hours associated with each weekday; and
3. the dates on which a version of that pattern applies.

It does not model clinics, theatre lists, patients, shifts, on-call cover, room allocation, or
staffing rotas.

## How this maps to the workbook

The workbook contains two related but different job-plan views.

The summary records overall job-plan PAs:

| Component | PAs |
| --- | ---: |
| DCC | 5.910 |
| SPA | 2.560 |
| Total | 8.470 |

These figures determine the proportion of annual entitlement allocated to DCC and SPA. They
reconcile exactly because `5.910 + 2.560 = 8.470`.

The annual-leave log separately records standard hours by weekday:

| Weekday | DCC hours | SPA hours |
| --- | ---: | ---: |
| Monday | 8.0 | 0.5 |
| Tuesday | 8.0 | 2.0 |
| Wednesday | 4.5 | 1.5 |
| Thursday | 0 | 0 |
| Friday | 0 | 0 |

These weekday values are used when a leave date is expanded into a daily deduction. For
example, ordinary leave on Monday starts from 8 DCC hours and 0.5 SPA hours.

The visible weekday values do not add up to the full weekly activity. In the supplied workbook,
the visible rows total `20.5 DCC / 4 SPA`, then operator-entered flexible amounts of `3 DCC / 4 SPA`
produce the displayed standard totals of `23.5 DCC / 8 SPA`. The application stores those flexible
amounts explicitly instead of hiding them in a formula.

Flexible hours contribute to the standard weekly totals, but are not assigned to a weekday. They
therefore do not create daily leave deductions. Only the visible weekday grid is used when a leave
date is booked. The operator remains responsible for entering the Trust-approved flexible amounts.

## Why weekday information is necessary

The overall `5.910 DCC / 2.560 SPA` split is not enough to calculate a leave entry. A Monday in
the workbook deducts a different number of hours from a Tuesday or Wednesday.

The application therefore stores a small weekly table equivalent to the workbook's standard
job-plan row. This is not the annual-leave ledger: the later ledger will look up the applicable
day in this table when a leave date is entered.

## Effective-dated versions

The workbook has “Job plan 1” and “Job plan 2”, each with From and To dates. The application
represents these as `JobPlanVersion` records.

When calculating a date, `JobPlanHistory` selects the version whose effective period contains
that date. Versions cannot overlap. A gap is allowed in stored history but causes an explicit
error if a calculation reaches it, rather than silently using the wrong pattern.

In the stored application, **Effective Until is exclusive**. A plan entered as 29 August 2025 to
29 August 2026 applies through 28 August 2026. This matches the calculation engine's date ranges
and prevents adjacent plans from overlapping on their handover date.

## One-week and multi-week patterns

Most consultants can use a one-week pattern. A multi-week cycle uses the same weekday table with
a week number, allowing a genuinely alternating pattern without adding rota concepts.

The cycle needs a Monday anchor date so the application can determine whether a calendar date is
in week 1, week 2, and so on. For a one-week pattern, the result is always week 1.

## Reconciliation

The application checks:

```text
DCC PAs + SPA PAs + Other PAs = total contracted PAs
```

If those figures do not agree, a written override reason is required. This preserves an approved
legacy exception without hiding it.

The application deliberately does not require visible weekday hours to equal contracted hours.
Doing so would incorrectly reject the supplied workbook's flexible activity arrangement.

## Exact arithmetic

All hours and PAs use `Decimal`. Enter `"5.910"`, not the float `5.910`, so small binary
floating-point errors cannot accumulate in leave balances.

## What the operator sees

The selected leave year contains a Job Plans section. **Add Job Plan** opens a focused editor with:

- the effective period;
- the overall DCC and SPA PAs, with Total PA calculated from them;
- a standard Monday-to-Friday hours grid, with weekends available when needed;
- additional flexible weekly DCC and SPA hours that are not tied to a weekday;
- an optional multi-week pattern; and
- an advanced Hours per PA field, which normally stays at four.

**Preview Job Plan** runs the existing calculation model without writing to SQLite. It shows the
allocated PA total, any difference from contracted PAs, the average visible hours, and the complete
standard weekly totals after flexible hours. A matching
PA split can be saved directly. A mismatch remains possible, but the operator must record why it
is being accepted. This follows the product rule that unusual policy situations should be visible
and explained rather than silently corrected.

Creating or editing a plan writes the complete PA split and daily pattern in one database
transaction. The change is also recorded in the append-only audit log. Plans cannot overlap and
must remain inside their selected leave year.

## Code layout

- `backend/src/job_plans/models.py` contains weekdays, daily activity, and repeating cycles.
- `backend/src/job_plans/versioning.py` contains effective versions and consultant history.
- `backend/src/job_plans/persistence.py` stores job-plan versions and their weekday rows.
- `backend/src/job_plans/schemas.py` validates API input and serializes exact decimals as strings.
- `backend/src/job_plans/service.py` adapts entered data to the calculation model, previews it, and
  saves accepted plans with audit events.
- `backend/src/job_plans/router.py` exposes the nested leave-year API.
- `backend/src/job_plans/__init__.py` contains the small public import surface.
- `frontend/src/jobPlans/` contains the typed API client and workbook-style editor.

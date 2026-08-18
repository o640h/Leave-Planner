# Annual Leave Calculation

This package calculates how much annual leave entitlement belongs to a consultant within one
leave year. It is intentionally a direct replacement for the small calculation block on the
workbook's `Master` sheet.

The implementation is in `backend/src/leave_calculation/`:

- `models.py` contains the calculation request, each dated calculation period, and the result.
- `calculator.py` performs date splitting, partial-year calculation, and DCC/SPA/Other allocation.
- `__init__.py` lists the small public interface used by later API and persistence code.

The package was named `leave_calculation` rather than `accrual`. In this project, "accrual" only
means calculating the share of an annual entitlement that applies to part of a year. The plainer
name is easier to find and does not imply payroll or accounting behaviour.

## What the workbook does

The workbook starts with one gross annual entitlement and two job-plan date periods:

| Workbook value | Job plan 1 | Job plan 2 |
| --- | ---: | ---: |
| From | 29 August 2025 | 1 August 2026 |
| To boundary | 1 August 2026 | 29 August 2026 |
| Number of days | 337 | 28 |
| Overall DCC PAs | 5.910 | 5.910 |
| Overall SPA PAs | 2.560 | 2.560 |

Its gross annual entitlement is `291.368` hours. The formula for each period is:

```text
period entitlement = annual entitlement x period calendar days / leave-year calendar days
```

That produces:

```text
291.368 x 337 / 365 = 269.0164821917808219... hours
291.368 x  28 / 365 =  22.3515178082191780... hours
```

The workbook then divides each result using the overall PA proportions:

```text
DCC share = period entitlement x 5.910 / 8.470
SPA share = period entitlement x 2.560 / 8.470
```

Across the complete leave year, this gives the workbook's `203.304` DCC hours and `88.064` SPA
hours before carry-forward. Carry-forward, public holidays, leave taken, and remaining balances
belong to later calculation areas; they are not hidden inside this package.

## An important date-boundary difference

The workbook displays `To` dates as the next period's boundary. Its formulas subtract dates, so
the first period is effectively `[29 August 2025, 1 August 2026)`: 1 August is not counted in job
plan 1. The second period is `[1 August 2026, 29 August 2026)`.

The operator-facing dates and the pure calculation engine's `DateRange` and effective-version
dates are inclusive. Persistence retains a half-open exclusive `effective_until` boundary, with
the frontend API adapter adding or subtracting one day so that this implementation detail is never
shown to the operator. The equivalent visible periods are therefore:

| Version | Inclusive start | Inclusive end |
| --- | --- | --- |
| Job plan 1 | 29 August 2025 | 31 July 2026 |
| Job plan 2 | 1 August 2026 | 28 August 2026 |

This conversion preserves `337 + 28 = 365` and prevents a one-day overlap. Any future workbook
comparison must account for this difference explicitly.

## What can cause a new calculation period

The app starts a fresh period only when an input that affects entitlement changes:

1. employment starts or ends;
2. a policy version changes;
3. the consultant reaches a service threshold used by that policy; or
4. a job-plan version changes.

Each period uses the annual entitlement rate and DCC/SPA/Other PA split that apply on its first
day. Its calendar-day share is then added to the leave-year total. This is the same calculation
as the workbook, repeated only when a consultant's conditions genuinely change during the year.

Multi-week weekday patterns do not make this calculation more complicated. They matter later,
when a leave booking is expanded into individual daily deductions. This package only needs the
overall contracted PAs from the applicable job-plan version.

## Policy entitlement versus the workbook's gross total

The current HR78 policy calculation gives a seven-year, 8.47-PA consultant `243.936` annual hours:

```text
288 policy hours x 8.47 / 10 = 243.936 hours
```

The workbook's `291.368` gross total includes `47.432` hours of public-holiday value. The integrated
application now calculates the `243.936` base and each applicable public holiday separately, then
adds them to the same `291.368` recommendation. Its detailed job-plan-period rows therefore show
base leave only; the future consultant-year summary will also show the workbook-style gross
`269.016 / 22.352` allocation for direct comparison.

## Exact arithmetic and display precision

All quantities use Python `Decimal`; floats are not used. Division may retain a tiny decimal
remainder far below the interface's display precision. The DCC, SPA, and Other amounts are built
so they add back to the source entitlement, and later presentation code will apply an explicit
display precision without changing stored source inputs.

## Renaming impact

Renaming the former `accrual` package required these code-level changes:

- imports now use `from leave_calculation import ...`;
- request/result names use `LeaveCalculation...`;
- the main function is `calculate_leave_entitlement`;
- partial-year apportionment is `calculate_partial_year_hours`;
- result fields use `entitlement_hours` rather than `accrued_hours`.

The package had no database tables, migrations, API routes, or frontend consumers, so nothing
outside its tests and documentation required conversion. Future code should use only the new
public names.

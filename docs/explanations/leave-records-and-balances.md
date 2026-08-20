# Leave Records and Balances

This part turns the dates an operator enters into the totals shown on screen. It is the software
equivalent of the workbook's leave tables and the purple **Leave Taken / Leave Remaining** box.

The implementation is in `backend/src/leave_records/`:

- `models.py` defines bookings, daily overrides, carry-forward, and calculated balance views;
- `expansion.py` turns each entered date range into individual calendar dates;
- `calculator.py` totals the deductions and explains the calculation; and
- `__init__.py` lists the names other backend code should import.

## Inputs and calculated values

On the workbook's Master sheet, yellow cells are generally operator inputs and green cells are
generally calculated outputs. The same separation is preserved in software, although formulas and
field meanings remain authoritative where workbook colours are inconsistent.

The operator supplies:

- a leave date range;
- its state: Planned, Approved, Taken, or Cancelled;
- an optional note;
- any partial-day replacement hours and the reason for changing them; and
- approved carry-forward from the previous leave year.

The software calculates:

- one daily row for every date in the range;
- the job-plan version applying on that date;
- the standard DCC, SPA, and Other hours for that weekday;
- the final deduction after any override; and
- projected, confirmed, and actual remaining balances.

A calculated balance is never typed in or silently edited. It can always be rebuilt from the
entitlement, public holidays, leave records, and carry-forward.

## Turning a range into daily deductions

Suppose an operator enters leave from Monday to Wednesday. The software expands that range to
three records, then looks up the effective job plan separately for each date. With the reference
workbook pattern, the standard deductions are:

| Day | DCC | SPA |
| --- | ---: | ---: |
| Monday | 8 | 0.5 |
| Tuesday | 8 | 2 |
| Wednesday | 4.5 | 1.5 |

Dates with no visible job-plan hours still produce a zero-hour daily record. Keeping the date is
useful for the calendar and history even though it does not reduce the balance.

If a job plan changes during a leave range, each date uses the version effective on that date. The
booking does not copy or freeze one weekday pattern for the whole range.

## Partial-day replacements

An override replaces only the categories supplied by the operator. For example, changing Tuesday
DCC from 8 to 4 while leaving SPA blank produces `4 DCC + 2 SPA`: the normal SPA value is kept.

An override must include a reason. This makes differences from the standard job plan visible and
traceable. The warning task will later flag unusual or overlapping records; it will not silently
change operator-entered values.

## The three balance views

| View | Leave states deducted | Meaning |
| --- | --- | --- |
| Projected | Planned, Approved, Taken | What remains if all current plans happen? |
| Confirmed | Approved, Taken | What remains after excluding tentative plans? |
| Actual | Taken | What has genuinely been consumed so far? |

Cancelled leave remains in the history but is excluded from all three deductions.

Every view uses the same calculation:

```text
remaining = annual entitlement
          + public-holiday entitlement
          + carry-forward
          - applicable public-holiday deductions
          - applicable booking deductions
```

## Carry-forward

Carry-forward is an approved number of unused hours brought into the next leave year. The operator
enters DCC and SPA separately so the opening balance retains the approved activity split. Neither
value can be negative, and entering zero in both fields clears it. The supplied workbook remains the
golden example with `41.25` DCC and zero SPA carry-forward.

The persisted workflow is implemented in `backend/src/carry_forward/` and currently appears
inside Annual Entitlement on the consultant Overview. Once leave-used and leave-remaining totals
are available, it belongs alongside that balance flow. Consultant corrections and sold leave are
not supported because they are not required by the supplied workbook.

## Why `ZERO_HOURS` exists

`ZERO_HOURS` is an exact `Hours(Decimal("0"))` value. It is not a configurable setting and is not
expected to change later.

Plain `0` is a Python integer. Using it as a default would mix integers with the `Hours` value
object and bypass the protection against floating-point calculations. The named constant avoids
repeatedly constructing the same immutable zero-hours object and makes the unit clear in code.

Because `Hours` is frozen (immutable), sharing this value is safe. The same idea is used for
`ZERO_ACTIVITY_HOURS`, which means zero DCC, zero SPA, and zero Other hours.

## Workbook reconciliation

The workbook records `213.5 DCC / 17 SPA` as ordinary leave and `16 DCC / 1 SPA` as applicable
public-holiday deductions. Together these reproduce its used totals of `229.5 DCC / 18 SPA`.

After adding `41.25` DCC carry-forward to opening entitlement of `203.304 DCC / 88.064 SPA`, the
actual remaining balance is exactly:

```text
DCC: 203.304 + 41.25 - 16 - 213.5 = 15.054 hours
SPA:  88.064 +  0.00 -  1 -  17.0 = 70.064 hours
```

The tests keep these values as the golden reference while separately documenting the workbook's
known malformed dates and formulas.

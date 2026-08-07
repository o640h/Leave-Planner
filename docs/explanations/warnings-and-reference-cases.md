# Warnings and Reference Cases

Warnings explain questionable planning data without changing a calculation or preventing the
operator from saving it. Structurally invalid data is still rejected by the model that owns it.

The warning implementation is `backend/src/leave_records/warnings.py`. The executable examples
are under `backend/tests/reference_cases/` so they do not add test data to the installed app.

## Current warnings

### Overlapping active bookings

Planned, Approved, and Taken bookings warn when their date ranges overlap. Cancelled records stay
in history but are ignored by this check. The warning records both booking IDs, both states, and
the shared dates so the operator can decide whether the records are duplicates.

### Negative balances

Each of the projected, confirmed, and actual views is checked independently:

- an **overdrawn** warning means the combined DCC, SPA, and Other balance is negative;
- an **activity imbalance** means the total is still non-negative, but at least one activity
  balance is negative.

This distinction matters because positive SPA hours must not hide an exhausted DCC allowance.

### Job-plan reconciliation overrides

A job-plan PA split normally reconciles exactly:

```text
DCC PAs + SPA PAs + Other PAs = contracted PAs
```

The job-plan model permits an authorised mismatch only when an override reason is stored. The
warning makes that exceptional decision visible during every affected leave-year period.

Visible weekday hours are deliberately not part of this warning. As demonstrated by the supplied
workbook, flexibly delivered activity means visible daily hours need not equal contracted hours.

### Carry-forward information

When carry-forward adjustments exist, an informational warning shows their DCC/SPA/Other total
and asks the operator to confirm local approval and use conditions. The engine does not currently
invent a maximum amount or expiry date.

## Rules deliberately deferred

The roadmap mentions notice periods, quarterly use, and carry-forward use. These are not encoded
as numeric rules yet:

- the current booking model does not store a request/submission date, so notice cannot be measured;
- quarterly targets and carry-forward deadlines require confirmed Trust thresholds; and
- team coverage warnings require the team/group configuration planned for the team-planning work.

These rules can be added later as versioned settings without changing existing warning IDs.

## Reference cases

### Supplied workbook

`workbook_reference_request()` recreates the reference consultant from source inputs: leave year,
two job-plan periods, overall PA split, visible weekday pattern, public-holiday treatment, entered
leave rows, and carry-forward. It preserves the entered hours but corrects the two obvious
decade-typo dates rather than importing invalid years.

Its checked outputs are:

| Result | DCC hours | SPA hours |
| --- | ---: | ---: |
| Opening entitlement | 203.304 | 88.064 |
| Carry-forward | 41.25 | 0 |
| Ordinary leave | 213.5 | 17 |
| Public-holiday deductions | 16 | 1 |
| Remaining | 15.054 | 70.064 |

### Synthetic full-time case

A 10-PA consultant works five eight-hour DCC days. The case verifies the full-time annual and
public-holiday entitlement, a normal Monday-to-Friday leave week, and a warning-free balance.

### Synthetic LTFT case

A 6-PA consultant works an uneven Monday/Tuesday pattern. The case verifies PA proration, the
visible hours of long working days, DCC/SPA splitting, approved carry-forward, and a public holiday
worked on site with its deduction retained.

### Synthetic capped multi-week case

A 12-PA consultant has two-week patterns, reaches seven years of consultant service during the
leave year, and changes job plan later in the year. The case proves that overall entitlement is
still capped at 10 PAs while activity proportions, effective dates, and daily deductions continue
to use the applicable 12-PA job plan.

## Property check

The lifecycle property test generates different numbers of Planned, Approved, and Taken bookings
and confirms this invariant for every generated example:

```text
projected deductions >= confirmed deductions >= actual deductions
```

This protects the meaning of the three balance views across more combinations than a few fixed
examples could cover.

# Public Holidays

This package handles England and Wales public holidays for one consultant leave year. It is kept
separate from the annual policy entitlement because HR78 says public holidays are additional to
consultant annual leave.

The implementation is in `backend/src/public_holidays/`:

- `models.py` contains calendars, manual corrections, consultant treatments, and results.
- `calendar.py` applies corrections and selects dates inside a period.
- `calculator.py` calculates entitlement and the standard weekday deduction.
- `snapshots.py` contains the dated offline England and Wales fallback.
- `gov_uk.py` parses and optionally downloads the official GOV.UK JSON feed.
- `__init__.py` defines the package's public imports.

The DCC/SPA/Other allocation function is shared through `backend/src/job_plans/allocation.py`, so
the annual policy calculation and public-holiday calculation cannot quietly develop different PA
allocation methods.

## The two public-holiday quantities

Every applicable holiday has two deliberately separate quantities.

### Entitlement added

HRS09 defines a public holiday as eight hours, or two PAs, for a full-time practitioner. For
medical staff this is one fifth of a 40-hour week. The value is prorated against ten PAs and capped
at the full-time value:

```text
public-holiday entitlement = 8 hours × minimum(contracted PAs, 10) ÷ 10
```

This amount is added for every official public holiday that falls inside both the leave year and
the consultant's period of employment. It does not depend on whether that weekday is normally
worked.

### Standard deduction

The deduction represents what the holiday consumes from the resulting leave allowance. For the
standard treatment, the calculation looks up the effective job plan on the holiday date and uses
that weekday's visible DCC, SPA, and Other hours.

A holiday on a normal non-working day therefore has a zero deduction. A holiday on a long Monday
can deduct more than a holiday on a shorter Wednesday. This is the same distinction shown by the
workbook: overall PAs calculate entitlement, while visible weekday hours calculate usage.

If an approved worked/on-call treatment retains the leave, the deduction is zero. The eight-hour
prorated entitlement is still added.

## Workbook reconciliation

The reference consultant has 8.470 contracted PAs and seven England and Wales holidays inside
the leave year from 29 August 2025 to 28 August 2026:

1. Christmas Day - 25 December 2025.
2. Boxing Day - 26 December 2025.
3. New Year's Day - 1 January 2026.
4. Good Friday - 3 April 2026.
5. Easter Monday - 6 April 2026.
6. Early May bank holiday - 4 May 2026.
7. Spring bank holiday - 25 May 2026.

The summer bank holiday on 31 August 2026 is outside that leave year. The added entitlement is:

```text
one holiday = 8 × 8.47 ÷ 10 = 6.776 hours
seven holidays = 7 × 6.776 = 47.432 hours

HR78 policy entitlement                 243.936 hours
public-holiday entitlement               47.432 hours
                                         -------
workbook gross entitlement              291.368 hours
```

Using the overall `5.910 DCC / 2.560 SPA` PA split, the holiday amount becomes `33.096` DCC hours
and `14.336` SPA hours.

In the workbook, Christmas Day, Boxing Day, New Year's Day, and Good Friday fall on weekdays with
no visible activity and deduct zero. Easter Monday and the spring holiday each deduct `8 DCC +
0.5 SPA`. The early-May holiday is marked on-call and retains its leave, so it also deducts zero.
The resulting public-holiday deduction is `16 DCC + 1 SPA = 17` hours.

## Worked and on-call treatment

The operator selects one of three treatments:

- `STANDARD` uses the normal weekday deduction;
- `WORKED_ON_SITE` retains the normal deduction; or
- `QUALIFYING_ON_CALL` retains the normal deduction.

A retained treatment requires an explanatory note. `worked_date` can record the actual attendance
date when it differs from the officially designated holiday date.

The software deliberately does not infer whether a shift or on-call period qualifies. HRS09's
introductory wording refers to attendance or significant disruption, while its example table also
awards a day for some formal on-call commitments without a call-in or disruption. That ambiguity
requires Trust policy-owner confirmation. Until confirmed, the operator records the approved
treatment and evidence rather than the software inventing a rule.

## Substitute holidays and avoiding duplicates

GOV.UK publishes the legally designated substitute weekday when Christmas Day, Boxing Day, or
New Year's Day falls on a weekend. The calendar stores that designated date, not both the original
weekend date and the substitute date.

If the consultant worked the original weekend day but the leave is retained against the substitute
holiday, `holiday_date` remains the designated GOV.UK holiday and `worked_date` records the actual
date worked. This supports HRS09's instruction not to award both the original and substitute date.

If one shift qualifies against two distinct public holidays, each official holiday receives its own
treatment record. This mirrors the policy examples without adding shift or rota modelling.

## Calendar sources and corrections

`ENGLAND_WALES_SNAPSHOT` is a dated offline copy covering 2025 through 2028. The application can
therefore calculate leave without internet access.

The optional synchronisation reads only the `england-and-wales` division from the fixed GOV.UK
JSON endpoint. It validates the response and limits its size. The downloader does not overwrite
saved data itself; later persistence/service code will store a successfully validated calendar and
retain the existing snapshot if synchronisation fails.

Manual corrections are stored separately from the base calendar. A correction can:

- add or replace a holiday with a required name and reason; or
- remove a holiday with a required reason.

Resolving a calendar applies those corrections to a copy, preserving the original source data for
audit purposes.

## Future integration

The public-holiday result currently exposes entitlement, DCC/SPA/Other allocation, standard
deductions, treatments, and a calculation trace. Persistence and the frontend will later provide
editing, caching, and audit history. The leave-ledger task will consume the calculated deductions;
it must not reimplement public-holiday policy.

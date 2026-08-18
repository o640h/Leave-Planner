# Consultant Entitlement Policy

This document explains how the application chooses a consultant's full-year annual-leave
entitlement. It is for maintainers who may need to inspect or update a policy version.

The implementation is in `backend/src/entitlement_policy/`:

- `models.py` defines reusable policy building blocks.
- `policy.py` selects policy versions and performs PA-based calculations.
- `hr78_v3.py` contains the actual HR78 version 3 consultant rules.
- `__init__.py` provides the package's public imports.

Most policy updates should create a new data file modelled on `hr78_v3.py`. The reusable
calculation machinery should only change when the underlying calculation method changes.

## The calculation in plain language

The low-level versioned policy model can answer three questions in order:

1. Which policy version applied on the calculation date?
2. Which appointment-era and completed-service tier applies to the consultant?
3. What proportion is due for their contracted programmed activities (PAs)?

The result is a full-year rate. The active operator workflow deliberately does not ask for an
appointment date or calculate an anniversary inside the year. It uses the post-April-2005
consultant tiers and one `Seven Years or More` confirmation for the complete leave year. The
low-level appointment-era data remains encoded so historical policy evidence is not discarded.

## HR78 version 3 consultant rules

HR78 section 7.4 gives the following entitlements. Public holidays are additional and are not
included here.

| Appointment date | Completed service in consultant grade | Total |
| --- | --- | ---: |
| Up to 31 March 2004 | Any | 34 days / 272 hours |
| 1 April 2004 to 31 March 2005 | Under 7 years | 34 days / 272 hours |
| 1 April 2004 to 31 March 2005 | 7 years or more | 35 days / 280 hours |
| From 1 April 2005 | Under 7 years | 34 days / 272 hours |
| From 1 April 2005 | 7 years or more | 36 days / 288 hours |

The code presents the total using the same named groups as the supplied workbook: Basic Leave,
Statutory Days, Hospital R&R, and any earned Seniority. This is easier to compare than one opaque
core figure:

| Tier total | Basic | Statutory | Hospital R&R | Seniority |
| --- | ---: | ---: | ---: | ---: |
| 272 hours | 240 | 16 | 16 | 0 |
| 280 hours | 240 | 16 | 16 | 8 |
| 288 hours | 240 | 16 | 16 | 16 |

`Hospital R&R` is the workbook label currently used for the policy's locally agreed allowance.
That mapping remains subject to Trust policy-owner confirmation; changing the label must not
silently change the historical policy version or total.

This makes the calculation trace understandable and allows a future policy to change one
component independently.

## PA proration and the cap

One PA is four hours. Annual entitlement is prorated against ten PAs and capped at ten PAs:

```text
factor = minimum(contracted PAs, 10) / 10
annual entitlement = full-time entitlement x factor
```

Examples:

| Contracted PAs | Factor | Result from a 288-hour tier |
| ---: | ---: | ---: |
| 6 | 0.6 | 172.8 hours |
| 8.47 | 0.847 | 243.936 hours |
| 10 | 1 | 288 hours |
| 12 | 1 | 288 hours |

PAs and hours use Python `Decimal`. Do not replace string values such as `"8.47"` with floats
such as `8.47`; binary floating point can introduce small errors into leave balances.

## How service tiers work

Each appointment era contains ordered service thresholds. Every era begins with a zero-year
tier. Some eras also have a seven-year tier.

The resolver selects the highest threshold already reached. Six completed years uses the
zero-year tier; exactly seven years uses the seven-year tier.

The package can still resolve completed-year thresholds for historical calculations. The active
recommendation supplies either the zero-year or seven-year tier directly from the operator's
checkbox, so it does not create a mid-year service milestone.

## Why policy versions are immutable

A saved calculation must continue to mean the same thing after a policy changes. Existing policy
objects are therefore immutable: updating policy means creating a new version, not editing a
historical object in place.

When a replacement policy is introduced:

1. Set the old version's `effective_to` to the day before the new policy starts.
2. Copy `hr78_v3.py` to a clearly named new policy file.
3. Give the new version a unique `version` value and confirmed effective date.
4. Change only the rules or source details that the new document actually changes.
5. Add both versions to the catalogue in chronological order.
6. Test the final day of the old version and first day of the new version.
7. Re-run all reference fixtures and obtain policy-owner confirmation.

Policy effective periods must not overlap. A calculation date must match exactly one version.

## Small source-wording assumptions

Two details are kept beside the encoded policy data so they remain easy to find:

- Section 7.4 uses both "from 1 April 2005" and "after 1 April 2005". The implementation treats
  1 April 2005 as part of the newer era so there is no one-day gap.
- The PDF says version 3 was ratified in July 2025 but gives no exact operational day. The
  working effective date is 1 July 2025.

They are small assumptions, but the Trust policy owner should confirm them before live use.

## What belongs elsewhere

This package does not calculate public holidays, employment-date proration, DCC/SPA allocation,
daily deductions, carry-forward, or balances. Those depend on calendars, job plans, and the
leave ledger, so they belong in their relevant calculation modules.

The workbook remains the golden worked example for later end-to-end verification. If a workbook
result disagrees with HR78, record and explain the difference rather than silently changing the
encoded policy.


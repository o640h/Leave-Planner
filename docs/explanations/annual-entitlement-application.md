# Annual Entitlement: Recommendation and Applied Value

## What this feature does

The application can now calculate a consultant's suggested annual-leave entitlement and let the
operator decide what value is actually used. This keeps the policy calculation helpful without
making it an unchangeable answer.

The workbook does the same broad job on its `Master` sheet:

- the annual entitlement, including bank holidays, is calculated;
- that entitlement is divided between DCC and SPA;
- carry-forward is added separately; and
- leave taken is subtracted from the resulting balance.

Carry-forward remains a separate opening-balance value beside the applied entitlement.
They affect the derived opening balance without rewriting the policy recommendation.

## The three sets of values

The entitlement screen deliberately keeps these values separate:

1. **Base Entitlement** is annual leave calculated from the applicable policy, service tier,
   employment period, and effective job plans.
2. **Public Holiday Entitlement** is the applicable public-holiday allowance calculated separately.
3. **Applied Entitlement** is the DCC and SPA opening balance that the operator has chosen to use.

The recommendation is the base entitlement plus public-holiday entitlement. The applied value is
what the leave ledger consumes. Saving an applied value never silently overwrites the calculation
that led to it.

For the supplied workbook example, the calculation is:

| Part | Hours |
| --- | ---: |
| Base annual leave | `243.936` |
| Public holidays | `47.432` |
| Recommended total | `291.368` |
| Recommended DCC | `203.304` |
| Recommended SPA | `88.064` |

Carry-forward is deliberately absent from this table because it is an adjustment, not part of the
policy recommendation.

## The operator's two choices

### Use Calculated Value

The application calculates the recommendation and applies the same DCC and SPA values. The
operator confirms only whether the consultant has seven years or more of service for the complete
selected leave year. Changing the checkbox clears the previous preview so the revised component and
total values must be reviewed before they can be applied.

### Enter Manually

The operator enters DCC and SPA hours without running the policy calculation. A reason is optional.
This supports a Trust-confirmed entitlement where the source facts needed for automatic calculation
are unavailable or the local decision is intentionally different.

`Other` activity remains supported internally for compatibility, but the interface currently applies
zero because the workbook workflow has not shown a need for an operator-editable Other value.

## Why the service choice is a checkbox

The workbook exposes one `Seniority (>7 yrs)` component rather than appointment and service dates.
The active recommendation follows that workflow directly: the operator confirms the service tier,
and that selection applies to the complete leave year. Employment dates remain separate and only
clip the period for an in-year joiner or leaver.

To reproduce the supplied workbook's `291.368` hours, select `Seven Years or More`. The resulting
calculation is:

```text
30 basic days + 2 statutory days + 2 seniority days + 2 local/R&R days = 36 days
36 days x 8 hours = 288 full-time hours before public holidays
288 x 8.47 PA / 10 PA = 243.936 base hours
7 public holidays x 8 hours x 8.47 PA / 10 PA = 47.432 holiday hours
243.936 + 47.432 = 291.368 recommended hours
```

The workbook labels the four groups separately, whereas HR78's encoded structure represents some
of those days through its core tier plus common statutory/local components. The total is the same.
Appointment-era distinctions remain documented in the versioned policy source, but they are not an
operator input or an active recommendation branch.

## Why the period rows differ from the workbook's accrued boxes

The detailed screen currently divides the **base** `243.936` hours across the two job-plan periods:

```text
243.936 x 337 / 365 = 225.223 hours
243.936 x  28 / 365 =  18.713 hours
```

The workbook's `Annual Leave accrued` boxes instead divide the **gross** `291.368` hours, including
public holidays, over the same periods:

```text
291.368 x 337 / 365 = 269.016 hours
291.368 x  28 / 365 =  22.352 hours
```

The application calculates each public holiday separately on its actual date, so its detailed
trace does not spread holiday hours evenly over every calendar day. Both methods reconcile to the
same `291.368` annual total and the same `203.304 DCC / 88.064 SPA` split in the supplied example.
The consultant-year summary will show a separate workbook-style period allocation so the operator
can compare the familiar accrued boxes without confusing them with the underlying holiday trace.

## End-to-end flow

1. The operator selects a consultant and leave year.
2. The frontend reads the entitlement workspace from the API.
3. For a calculated mode, the service loads the leave year and its effective job plans, then calls
   the existing policy, partial-year, and public-holiday calculation functions.
4. The API returns the named Basic Leave, Statutory Days, Hospital R&R and Seniority components,
   the public-holiday component, total recommendation, rule versions, source details, and grouped
   calculation explanations.
5. The operator reviews the result and either applies it unchanged or enters a manual value. An
   optional reason can be stored with a manual value.
6. The backend stores an immutable recommendation snapshot where one exists and stores the current
   applied entitlement separately.
7. The leave-record calculator receives only the applied DCC/SPA/Other opening values. It does not
   need to know how the operator chose them.

This separation is important: policy rules may produce a recommendation, but only an explicit
operator action changes the opening value used by balances.

## Stored records

`EntitlementRecommendationRecord` keeps the exact inputs, component values, policy/source metadata,
and trace that produced a recommendation. Old snapshots remain available for audit.

`AppliedEntitlementRecord` keeps one current application for each leave year: its mode, applied DCC,
SPA and Other hours, optional recommendation link, reason, and update time.

Migration `0012` converts stored date inputs to the equivalent seven-year selection at the active
leave-year start. Existing calculated overrides become manual applications so their applied hours,
reason, and linked historical recommendation are preserved without retaining a removed mode.

Decimal quantities are stored and transferred without binary floating point. The interface removes
unnecessary trailing zeroes for readability, but the stored precision is retained.

## API endpoints

All endpoints sit below:

`/api/consultants/{consultant_id}/leave-years/{leave_year_id}/entitlement`

- `GET` returns the latest recommendation and current applied value together.
- `POST /preview` calculates a recommendation without applying it.
- `POST /refresh` recalculates an existing recommendation after a source configuration changes.
- `PUT` applies the selected calculated or manual value.

Saving a changed leave year or job plan calls the refresh endpoint. Calculated mode updates both
the recommendation and applied opening entitlement. Manual mode is never overwritten. If the new
configuration is incomplete, the previous applied value remains visible while the interface
explains what must be corrected.

## Where to change the behaviour

- `backend/src/annual_entitlement/service.py` coordinates the existing calculators and persistence.
- `backend/src/annual_entitlement/schemas.py` defines the API inputs and outputs.
- `backend/src/annual_entitlement/persistence.py` defines recommendation and application records.
- `backend/src/entitlement_policy/` contains the versioned policy rules.
- `backend/src/leave_calculation/` handles partial-year and effective-date calculations.
- `backend/src/public_holidays/` calculates the separate holiday component.
- `backend/src/leave_records/calculator.py` uses the final applied entitlement.
- `frontend/src/annualEntitlement/` contains the operator workflow and calculation trace.

When policy rules change, add a new dated policy version rather than editing a version already used
by a stored recommendation. This keeps historical explanations reproducible.

## Current boundary

The calculation uses the persisted dated England and Wales calendar, active Trust corrections, and
the selected qualifying-on-call treatments. The interface leads with workbook-relevant component and
period totals; individual holiday occurrences and policy metadata sit in separate disclosures.
These are still working rule interpretations and must not be treated as final policy sign-off.

The following `Master`-sheet information is not yet displayed or maintained by the current vertical
slices:

- dated leave entries, weekday counts, leave used, and leave remaining;
- annual leave calculated for each individual job-plan period and its calendar-day count;
- a separate job-plan review date, if the operator confirms this must remain distinct from the
  effective dates; and
- the final combined consultant-year statement that brings all of those values together.

Consultant identity, post title, leave-year dates, multiple effective job plans, DCC/SPA/Total PA,
base entitlement, public-holiday entitlement, recommended entitlement, and the applied opening
value are already present.

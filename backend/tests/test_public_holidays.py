"""Tests for England and Wales public-holiday calculations.

The reference tests mirror the supplied workbook: seven holidays fall inside
the leave year, each adds an eight-hour value prorated to 8.47 PAs, and the
early-May holiday is retained because the workbook marks it as on-call.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from typing import Any, Self, cast
from urllib.request import Request

import pytest

from domain import ActivityType, DateRange, Hours, ProgrammedActivities, RuleId
from job_plans import (
    ActivityAllocation,
    JobPlanCycle,
    JobPlanDay,
    JobPlanHistory,
    JobPlanVersion,
    Weekday,
    allocate_hours_by_pa,
)
from public_holidays import (
    ENGLAND_WALES_SNAPSHOT,
    HolidayCalendarSource,
    HolidayCorrectionAction,
    HolidayTreatmentBasis,
    PublicHoliday,
    PublicHolidayCalendar,
    PublicHolidayCorrection,
    PublicHolidayRequest,
    PublicHolidayResult,
    PublicHolidayTreatment,
    calculate_public_holidays,
    fetch_gov_uk_calendar,
    gov_uk,
    holidays_in_period,
    parse_gov_uk_calendar,
    resolved_holidays,
)


def _activity(activity_type: ActivityType, hours: str) -> ActivityAllocation:
    return ActivityAllocation(activity_type, Hours.from_value(hours))


def _workbook_cycle() -> JobPlanCycle:
    """Build the visible weekday pattern and overall PA split from Excel."""

    days = [JobPlanDay(1, weekday) for weekday in Weekday]
    days[Weekday.MONDAY] = JobPlanDay(
        1,
        Weekday.MONDAY,
        (
            _activity(ActivityType.DCC, "8"),
            _activity(ActivityType.SPA, "0.5"),
        ),
    )
    days[Weekday.TUESDAY] = JobPlanDay(
        1,
        Weekday.TUESDAY,
        (
            _activity(ActivityType.DCC, "8"),
            _activity(ActivityType.SPA, "2"),
        ),
    )
    days[Weekday.WEDNESDAY] = JobPlanDay(
        1,
        Weekday.WEDNESDAY,
        (
            _activity(ActivityType.DCC, "4.5"),
            _activity(ActivityType.SPA, "1.5"),
        ),
    )

    return JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value("8.470"),
        dcc_pas=ProgrammedActivities.from_value("5.910"),
        spa_pas=ProgrammedActivities.from_value("2.560"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(days),
    )


def _cycle_for_pas(programmed_activities: str) -> JobPlanCycle:
    """Create a simple all-DCC plan for PA-cap examples."""

    return JobPlanCycle(
        week_count=1,
        contracted_pas=ProgrammedActivities.from_value(programmed_activities),
        dcc_pas=ProgrammedActivities.from_value(programmed_activities),
        spa_pas=ProgrammedActivities.from_value("0"),
        other_pas=ProgrammedActivities.from_value("0"),
        hours_per_pa=Hours.from_value("4"),
        days=tuple(JobPlanDay(1, weekday) for weekday in Weekday),
    )


def _job_plan(
    *,
    version_id: str,
    effective_from: date,
    effective_to: date | None,
    cycle: JobPlanCycle,
) -> JobPlanVersion:
    anchor = effective_from
    while anchor.weekday() != Weekday.MONDAY:
        anchor = date.fromordinal(anchor.toordinal() - 1)

    return JobPlanVersion(
        version_id=RuleId(version_id),
        effective_from=effective_from,
        effective_to=effective_to,
        cycle_anchor_date=anchor,
        cycle=cycle,
    )


def _workbook_job_plans() -> JobPlanHistory:
    cycle = _workbook_cycle()
    return JobPlanHistory(
        (
            _job_plan(
                version_id="job-plan.workbook.1",
                effective_from=date(2025, 8, 29),
                effective_to=date(2026, 7, 31),
                cycle=cycle,
            ),
            _job_plan(
                version_id="job-plan.workbook.2",
                effective_from=date(2026, 8, 1),
                effective_to=None,
                cycle=cycle,
            ),
        )
    )


def _calendar(
    *holidays: PublicHoliday,
    corrections: tuple[PublicHolidayCorrection, ...] = (),
) -> PublicHolidayCalendar:
    return PublicHolidayCalendar(
        source=HolidayCalendarSource.STATIC_SNAPSHOT,
        source_date=date(2026, 8, 6),
        holidays=tuple(sorted(holidays, key=lambda holiday: holiday.holiday_date)),
        corrections=corrections,
    )


def _request(
    *,
    calendar: PublicHolidayCalendar = ENGLAND_WALES_SNAPSHOT,
    employment_start: date = date(2010, 1, 1),
    employment_end: date | None = None,
    job_plans: JobPlanHistory | None = None,
    treatments: tuple[PublicHolidayTreatment, ...] = (),
) -> PublicHolidayRequest:
    return PublicHolidayRequest(
        leave_year=DateRange(date(2025, 8, 29), date(2026, 8, 28)),
        employment_start=employment_start,
        employment_end=employment_end,
        calendar=calendar,
        job_plans=job_plans or _workbook_job_plans(),
        treatments=treatments,
    )


def test_snapshot_contains_the_seven_workbook_holidays() -> None:
    """The summer holiday on 31 August falls outside this leave year."""

    holidays = holidays_in_period(
        ENGLAND_WALES_SNAPSHOT,
        DateRange(date(2025, 8, 29), date(2026, 8, 28)),
    )

    assert tuple(holiday.holiday_date for holiday in holidays) == (
        date(2025, 12, 25),
        date(2025, 12, 26),
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 4),
        date(2026, 5, 25),
    )


def test_workbook_public_holiday_entitlement_reconciles_gross_total() -> None:
    """Seven holidays add exactly 47.432 hours to 243.936 policy hours."""

    treatment = PublicHolidayTreatment(
        holiday_date=date(2026, 5, 4),
        basis=HolidayTreatmentBasis.QUALIFYING_ON_CALL,
        note="Workbook marks this holiday as on-call",
    )

    result = calculate_public_holidays(_request(treatments=(treatment,)))

    assert len(result.value.occurrences) == 7
    assert result.value.entitlement_hours == Hours.from_value("47.432")
    assert result.value.dcc_entitlement_hours == Hours.from_value("33.096")
    assert result.value.spa_entitlement_hours == Hours.from_value("14.336")
    assert result.value.other_entitlement_hours == Hours.from_value("0")
    assert Hours.from_value("243.936") + result.value.entitlement_hours == Hours.from_value(
        "291.368"
    )


def test_workbook_holiday_deductions_follow_weekdays_and_retention() -> None:
    """Only two Mondays consume hours because the early-May Monday is retained."""

    treatment = PublicHolidayTreatment(
        holiday_date=date(2026, 5, 4),
        basis=HolidayTreatmentBasis.QUALIFYING_ON_CALL,
        note="Qualifying on-call commitment",
        worked_date=date(2026, 5, 4),
    )
    result = calculate_public_holidays(_request(treatments=(treatment,))).value
    occurrences = {occurrence.holiday.holiday_date: occurrence for occurrence in result.occurrences}

    assert occurrences[date(2026, 4, 6)].dcc_deduction_hours == Hours.from_value("8")
    assert occurrences[date(2026, 4, 6)].spa_deduction_hours == Hours.from_value("0.5")
    assert occurrences[date(2026, 5, 4)].deduction_hours == Hours.from_value("0")
    assert occurrences[date(2026, 5, 25)].deduction_hours == Hours.from_value("8.5")
    assert result.deduction_hours == Hours.from_value("17")


def test_only_holidays_during_employment_are_included() -> None:
    """HR78 excludes holidays outside the period of employment."""

    result = calculate_public_holidays(
        _request(
            employment_start=date(2026, 4, 4),
            employment_end=date(2026, 5, 4),
        )
    ).value

    assert tuple(occurrence.holiday.holiday_date for occurrence in result.occurrences) == (
        date(2026, 4, 6),
        date(2026, 5, 4),
    )
    assert result.entitlement_hours == Hours.from_value("13.552")


@pytest.mark.parametrize(
    ("contracted_pas", "expected_hours"),
    [
        ("0", "0"),
        ("6", "4.8"),
        ("10", "8"),
        # Entitlement is capped at the full-time 10-PA value.
        ("12", "8"),
    ],
)
def test_eight_hour_value_is_prorated_and_capped(
    contracted_pas: str,
    expected_hours: str,
) -> None:
    holiday = PublicHoliday(date(2026, 1, 1), "New Year's Day")
    cycle = _cycle_for_pas(contracted_pas)
    history = JobPlanHistory(
        (
            _job_plan(
                version_id="job-plan.pa-example",
                effective_from=date(2025, 8, 29),
                effective_to=None,
                cycle=cycle,
            ),
        )
    )

    result = calculate_public_holidays(
        _request(calendar=_calendar(holiday), job_plans=history)
    ).value

    assert result.entitlement_hours == Hours.from_value(expected_hours)


def test_manual_corrections_add_replace_and_remove_without_mutating_source() -> None:
    original_new_year = PublicHoliday(date(2026, 1, 1), "New Year's Day")
    original_christmas = PublicHoliday(date(2026, 12, 25), "Christmas Day")
    calendar = _calendar(
        original_new_year,
        original_christmas,
        corrections=(
            PublicHolidayCorrection(
                date(2026, 1, 1),
                HolidayCorrectionAction.REMOVE,
                "Trust does not observe this date",
            ),
            PublicHolidayCorrection(
                date(2026, 6, 15),
                HolidayCorrectionAction.ADD_OR_REPLACE,
                "Locally confirmed additional holiday",
                "Trust public holiday",
            ),
            PublicHolidayCorrection(
                date(2026, 12, 25),
                HolidayCorrectionAction.ADD_OR_REPLACE,
                "Correct local display name",
                "Christmas public holiday",
            ),
        ),
    )

    resolved = resolved_holidays(calendar)

    assert calendar.holidays == (original_new_year, original_christmas)
    assert tuple((holiday.holiday_date, holiday.name) for holiday in resolved) == (
        (date(2026, 6, 15), "Trust public holiday"),
        (date(2026, 12, 25), "Christmas public holiday"),
    )
    assert "Locally confirmed" in resolved[0].notes


def test_retained_treatments_require_a_note_and_do_not_infer_eligibility() -> None:
    """The operator records the approved result of the ambiguous on-call rule."""

    standard = PublicHolidayTreatment(date(2026, 5, 4), HolidayTreatmentBasis.STANDARD)
    worked = PublicHolidayTreatment(
        date(2026, 5, 4),
        HolidayTreatmentBasis.WORKED_ON_SITE,
        note="Worked 08:00 to 17:00 on site",
    )

    assert not standard.retains_leave
    assert worked.retains_leave
    with pytest.raises(ValueError, match="explanatory note"):
        PublicHolidayTreatment(date(2026, 5, 4), HolidayTreatmentBasis.QUALIFYING_ON_CALL)


def test_empty_employment_period_returns_no_holidays_or_trace() -> None:
    result = calculate_public_holidays(_request(employment_start=date(2027, 1, 1)))

    assert result.value == PublicHolidayResult(occurrences=())
    assert result.trace == ()


def test_unknown_treatment_date_is_rejected() -> None:
    treatment = PublicHolidayTreatment(date(2026, 2, 1), HolidayTreatmentBasis.STANDARD)

    with pytest.raises(ValueError, match="not public holidays"):
        calculate_public_holidays(_request(treatments=(treatment,)))


def test_trace_records_entitlement_deduction_and_retention() -> None:
    treatment = PublicHolidayTreatment(
        date(2026, 5, 4),
        HolidayTreatmentBasis.WORKED_ON_SITE,
        note="Worked on site",
    )

    result = calculate_public_holidays(_request(treatments=(treatment,)))
    trace_by_date = {step.effective_date: step for step in result.trace}
    may_trace = trace_by_date[date(2026, 5, 4)]

    assert may_trace.rule_id == RuleId("public-holiday.standard-eight-hours")
    assert may_trace.amount == Hours.from_value("6.776")
    assert may_trace.context["retains_leave"] == "true"
    assert may_trace.context["deduction_hours"] == "0"


def test_shared_pa_allocator_preserves_the_source_total() -> None:
    """The Task 4 refactor must retain its exact-allocation guarantee."""

    cycle = _workbook_cycle()
    dcc, spa, other = allocate_hours_by_pa(Hours.from_value("47.432"), cycle)

    assert dcc == Hours.from_value("33.096")
    assert spa == Hours.from_value("14.336")
    assert other == Hours.from_value("0")
    assert dcc + spa + other == Hours.from_value("47.432")


def test_gov_uk_parser_selects_england_and_wales_and_sorts_events() -> None:
    payload = json.dumps(
        {
            "england-and-wales": {
                "division": "england-and-wales",
                "events": [
                    {
                        "title": "Boxing Day",
                        "date": "2026-12-28",
                        "notes": "Substitute day",
                    },
                    {
                        "title": "Christmas Day",
                        "date": "2026-12-25",
                        "notes": "",
                    },
                ],
            },
            "scotland": {
                "events": [
                    {
                        "title": "Scotland-only holiday",
                        "date": "2026-11-30",
                        "notes": "",
                    }
                ]
            },
        }
    )

    calendar = parse_gov_uk_calendar(payload, source_date=date(2026, 8, 6))

    assert calendar.source is HolidayCalendarSource.GOV_UK_SYNC
    assert tuple(holiday.name for holiday in calendar.holidays) == (
        "Christmas Day",
        "Boxing Day",
    )
    assert calendar.holidays[1].notes == "Substitute day"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json", "invalid JSON"),
        ("[]", "JSON object"),
        ("{}", "missing England and Wales"),
        ('{"england-and-wales": {}}', "events must be a list"),
        ('{"england-and-wales": {"events": [1]}}', "event must be an object"),
        (
            '{"england-and-wales": {"events": [{"title": "", "date": "2026-01-01"}]}}',
            "title cannot be empty",
        ),
        (
            '{"england-and-wales": {"events": [{"title": "Holiday", "date": 1}]}}',
            "date must be text",
        ),
        (
            '{"england-and-wales": {"events": [{"title": "Holiday", "date": "bad"}]}}',
            "Invalid GOV.UK holiday date",
        ),
        (
            '{"england-and-wales": {"events": '
            '[{"title": "Holiday", "date": "2026-01-01", "notes": 1}]}}',
            "notes must be text",
        ),
    ],
)
def test_gov_uk_parser_rejects_malformed_data(payload: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_gov_uk_calendar(payload, source_date=date(2026, 8, 6))


class _FakeResponse:
    """Small context manager used to test downloading without internet access."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.payload[:size]


def test_fetch_uses_the_fixed_gov_uk_url_and_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (
        b'{"england-and-wales":{"events":[{"title":"New Year","date":"2026-01-01","notes":""}]}}'
    )
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse(payload)

    monkeypatch.setattr(gov_uk, "urlopen", fake_urlopen)

    calendar = fetch_gov_uk_calendar(source_date=date(2026, 8, 6), timeout_seconds=4.5)

    assert captured == {
        "url": "https://www.gov.uk/bank-holidays.json",
        "timeout": 4.5,
    }
    assert calendar.holidays[0].holiday_date == date(2026, 1, 1)


def test_fetch_rejects_invalid_timeout_and_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        fetch_gov_uk_calendar(source_date=date(2026, 8, 6), timeout_seconds=0)

    def oversized_urlopen(request: Request, timeout: float) -> _FakeResponse:
        del request, timeout
        return _FakeResponse(b"x" * (1_000_001))

    monkeypatch.setattr(gov_uk, "urlopen", oversized_urlopen)
    with pytest.raises(ValueError, match="size limit"):
        fetch_gov_uk_calendar(source_date=date(2026, 8, 6))


@pytest.mark.parametrize(
    ("changes", "error_type", "message"),
    [
        ({"holiday_date": cast(Any, datetime(2026, 1, 1))}, TypeError, "date"),
        ({"name": " "}, ValueError, "name"),
        ({"notes": cast(Any, None)}, TypeError, "notes"),
    ],
)
def test_public_holiday_validation(
    changes: dict[str, Any],
    error_type: type[Exception],
    message: str,
) -> None:
    holiday = PublicHoliday(date(2026, 1, 1), "New Year's Day")
    with pytest.raises(error_type, match=message):
        replace(holiday, **changes)


def test_calendar_and_correction_validation() -> None:
    holiday = PublicHoliday(date(2026, 1, 1), "New Year's Day")

    with pytest.raises(ValueError, match="chronological"):
        PublicHolidayCalendar(
            HolidayCalendarSource.STATIC_SNAPSHOT,
            date(2026, 8, 6),
            (PublicHoliday(date(2026, 12, 25), "Christmas"), holiday),
        )
    with pytest.raises(ValueError, match="duplicate holiday"):
        PublicHolidayCalendar(
            HolidayCalendarSource.STATIC_SNAPSHOT,
            date(2026, 8, 6),
            (holiday, holiday),
        )
    with pytest.raises(ValueError, match="requires a name"):
        PublicHolidayCorrection(
            date(2026, 1, 1),
            HolidayCorrectionAction.ADD_OR_REPLACE,
            "Reason",
        )
    with pytest.raises(ValueError, match="cannot have"):
        PublicHolidayCorrection(
            date(2026, 1, 1),
            HolidayCorrectionAction.REMOVE,
            "Reason",
            "Unexpected name",
        )


def test_request_and_public_functions_reject_invalid_inputs() -> None:
    request = _request()

    with pytest.raises(ValueError, match="more than one treatment"):
        replace(
            request,
            treatments=(
                PublicHolidayTreatment(date(2026, 1, 1), HolidayTreatmentBasis.STANDARD),
                PublicHolidayTreatment(date(2026, 1, 1), HolidayTreatmentBasis.STANDARD),
            ),
        )
    with pytest.raises(TypeError, match="PublicHolidayRequest"):
        calculate_public_holidays(cast(Any, "bad"))
    with pytest.raises(TypeError, match="PublicHolidayCalendar"):
        resolved_holidays(cast(Any, "bad"))
    with pytest.raises(TypeError, match="DateRange"):
        holidays_in_period(ENGLAND_WALES_SNAPSHOT, cast(Any, "bad"))
    with pytest.raises(TypeError, match="bytes or text"):
        parse_gov_uk_calendar(cast(Any, {}), source_date=date(2026, 8, 6))
    with pytest.raises(TypeError, match="source_date"):
        parse_gov_uk_calendar("{}", source_date=cast(Any, datetime(2026, 8, 6)))

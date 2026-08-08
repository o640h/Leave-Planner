"""Public-holiday calculations plus strict validation at the GOV.UK boundary."""

import json
from dataclasses import replace
from datetime import date
from typing import Self
from urllib.request import Request

import pytest
from reference_cases import workbook_reference_request
from reference_cases.common import cycle, job_plan

from domain import DateRange, Hours
from job_plans import JobPlanHistory, allocate_hours_by_pa
from public_holidays import (
    ENGLAND_WALES_SNAPSHOT,
    HolidayCalendarSource,
    HolidayCorrectionAction,
    HolidayTreatmentBasis,
    PublicHoliday,
    PublicHolidayCalendar,
    PublicHolidayCorrection,
    PublicHolidayRequest,
    PublicHolidayTreatment,
    calculate_public_holidays,
    fetch_gov_uk_calendar,
    gov_uk,
    parse_gov_uk_calendar,
    resolved_holidays,
)

LEAVE_YEAR = DateRange(date(2025, 8, 29), date(2026, 8, 28))


def workbook_holiday_request() -> PublicHolidayRequest:
    source = workbook_reference_request()
    return PublicHolidayRequest(
        leave_year=LEAVE_YEAR,
        employment_start=date(2010, 1, 1),
        employment_end=None,
        calendar=ENGLAND_WALES_SNAPSHOT,
        job_plans=source.job_plans,
        treatments=(
            PublicHolidayTreatment(
                date(2026, 5, 4),
                HolidayTreatmentBasis.QUALIFYING_ON_CALL,
                note="Workbook marks this holiday as on-call",
            ),
        ),
    )


def test_snapshot_and_workbook_totals_match_excel() -> None:
    result = calculate_public_holidays(workbook_holiday_request()).value
    assert len(result.occurrences) == 7
    assert result.entitlement_hours == Hours.from_value("47.432")
    assert result.dcc_entitlement_hours == Hours.from_value("33.096")
    assert result.spa_entitlement_hours == Hours.from_value("14.336")
    assert result.deduction_hours == Hours.from_value("17")


def test_holiday_deductions_follow_visible_weekday_hours() -> None:
    result = calculate_public_holidays(workbook_holiday_request()).value
    by_date = {item.holiday.holiday_date: item for item in result.occurrences}
    assert by_date[date(2026, 4, 6)].deduction_hours == Hours.from_value("8.5")
    assert by_date[date(2026, 5, 4)].deduction_hours == Hours.from_value("0")
    assert by_date[date(2026, 5, 25)].deduction_hours == Hours.from_value("8.5")


@pytest.mark.parametrize(("pas", "expected"), [("6", "4.8"), ("10", "8"), ("12", "8")])
def test_eight_hour_value_is_pa_prorated_and_capped(pas: str, expected: str) -> None:
    plan = cycle(week_count=1, contracted_pas=pas, dcc_pas=pas, spa_pas="0")
    history = JobPlanHistory(
        (
            job_plan(
                version_id="job-plan.holiday",
                effective_from=date(2026, 1, 1),
                effective_to=None,
                job_cycle=plan,
            ),
        )
    )
    calendar = PublicHolidayCalendar(
        HolidayCalendarSource.STATIC_SNAPSHOT,
        date(2026, 1, 1),
        (PublicHoliday(date(2026, 1, 1), "New Year"),),
    )
    request = PublicHolidayRequest(
        DateRange(date(2026, 1, 1), date(2026, 12, 31)),
        date(2010, 1, 1),
        None,
        calendar,
        history,
    )
    assert calculate_public_holidays(request).value.entitlement_hours == Hours.from_value(expected)


def test_employment_dates_filter_holidays() -> None:
    request = replace(
        workbook_holiday_request(),
        employment_start=date(2026, 4, 1),
        employment_end=date(2026, 5, 31),
    )
    dates = tuple(
        item.holiday.holiday_date for item in calculate_public_holidays(request).value.occurrences
    )
    assert dates == (date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25))


def test_manual_corrections_preserve_the_base_snapshot() -> None:
    base = (
        PublicHoliday(date(2026, 1, 1), "New Year"),
        PublicHoliday(date(2026, 12, 25), "Christmas"),
    )
    calendar = PublicHolidayCalendar(
        HolidayCalendarSource.STATIC_SNAPSHOT,
        date(2026, 1, 1),
        base,
        (
            PublicHolidayCorrection(
                date(2026, 1, 1), HolidayCorrectionAction.REMOVE, "Local change"
            ),
            PublicHolidayCorrection(
                date(2026, 12, 25),
                HolidayCorrectionAction.ADD_OR_REPLACE,
                "Rename",
                "Christmas Substitute",
            ),
        ),
    )
    assert tuple(item.name for item in resolved_holidays(calendar)) == ("Christmas Substitute",)
    assert calendar.holidays == base


def test_retained_treatment_requires_an_operator_note() -> None:
    with pytest.raises(ValueError, match="note"):
        PublicHolidayTreatment(date(2026, 1, 1), HolidayTreatmentBasis.WORKED_ON_SITE)
    with pytest.raises(ValueError, match="more than one"):
        replace(
            workbook_holiday_request(),
            treatments=(
                PublicHolidayTreatment(date(2026, 1, 1), HolidayTreatmentBasis.STANDARD),
                PublicHolidayTreatment(date(2026, 1, 1), HolidayTreatmentBasis.STANDARD),
            ),
        )


def test_pa_allocator_preserves_the_source_total() -> None:
    plan = workbook_holiday_request().job_plans.versions[0].cycle
    parts = allocate_hours_by_pa(Hours.from_value("47.432"), plan)
    assert parts == (Hours.from_value("33.096"), Hours.from_value("14.336"), Hours.from_value("0"))
    assert sum((part.value for part in parts), start=0) == Hours.from_value("47.432").value


def test_gov_uk_parser_selects_and_sorts_england_and_wales() -> None:
    payload = json.dumps(
        {
            "england-and-wales": {
                "events": [
                    {"title": "Boxing Day", "date": "2026-12-28", "notes": "Substitute day"},
                    {"title": "Christmas Day", "date": "2026-12-25", "notes": ""},
                ]
            },
            "scotland": {"events": [{"title": "Scotland only", "date": "2026-11-30"}]},
        }
    )
    calendar = parse_gov_uk_calendar(payload, source_date=date(2026, 8, 6))
    assert calendar.source is HolidayCalendarSource.GOV_UK_SYNC
    assert tuple(item.name for item in calendar.holidays) == ("Christmas Day", "Boxing Day")


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        "{}",
        '{"england-and-wales": {}}',
        '{"england-and-wales": {"events": [1]}}',
        '{"england-and-wales": {"events": [{"title": "", "date": "2026-01-01"}]}}',
        '{"england-and-wales": {"events": [{"title": "Holiday", "date": "bad"}]}}',
    ],
)
def test_gov_uk_parser_rejects_malformed_external_data(payload: str) -> None:
    with pytest.raises(ValueError):
        parse_gov_uk_calendar(payload, source_date=date(2026, 8, 6))


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.payload[:size]


def test_fetch_uses_the_fixed_gov_uk_url(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'{"england-and-wales":{"events":[{"title":"New Year","date":"2026-01-01","notes":""}]}}'
    )
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        captured.update(url=request.full_url, timeout=timeout)
        return FakeResponse(payload)

    monkeypatch.setattr(gov_uk, "urlopen", fake_urlopen)
    calendar = fetch_gov_uk_calendar(source_date=date(2026, 8, 6), timeout_seconds=4.5)
    assert captured == {"url": "https://www.gov.uk/bank-holidays.json", "timeout": 4.5}
    assert calendar.holidays[0].holiday_date == date(2026, 1, 1)

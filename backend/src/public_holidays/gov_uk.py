"""Import of the official GOV.UK public-holiday JSON feed."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from .models import (
    HolidayCalendarSource,
    PublicHoliday,
    PublicHolidayCalendar,
)

GOV_UK_BANK_HOLIDAYS_URL = "https://www.gov.uk/bank-holidays.json"
_MAX_RESPONSE_BYTES = 1_000_000


def parse_gov_uk_calendar(
    payload: bytes | str,
    *,
    source_date: date,
) -> PublicHolidayCalendar:
    """Parse only the England and Wales division."""

    if not isinstance(payload, bytes | str):
        raise TypeError("GOV.UK payload must be bytes or text")

    if type(source_date) is not date:
        raise TypeError("source_date must be a date")

    try:
        decoded: Any = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("GOV.UK returned invalid JSON") from error

    if not isinstance(decoded, dict):
        raise ValueError("GOV.UK payload must contain a JSON object")

    division = decoded.get("england-and-wales")
    if not isinstance(division, dict):
        raise ValueError("GOV.UK payload is missing England and Wales")

    events = division.get("events")
    if not isinstance(events, list):
        raise ValueError("England and Wales events must be a list")

    holidays: list[PublicHoliday] = []

    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Each GOV.UK holiday event must be an object")

        title = event.get("title")
        date_text = event.get("date")
        notes = event.get("notes", "")

        if not isinstance(title, str) or not title.strip():
            raise ValueError("GOV.UK holiday title cannot be empty")

        if not isinstance(date_text, str):
            raise ValueError("GOV.UK holiday date must be text")

        if not isinstance(notes, str):
            raise ValueError("GOV.UK holiday notes must be text")

        try:
            holiday_date = date.fromisoformat(date_text)
        except ValueError as error:
            raise ValueError(f"Invalid GOV.UK holiday date: {date_text!r}") from error

        holidays.append(
            PublicHoliday(
                holiday_date=holiday_date,
                name=title,
                notes=notes,
            )
        )

    holidays.sort(key=lambda holiday: holiday.holiday_date)

    return PublicHolidayCalendar(
        source=HolidayCalendarSource.GOV_UK_SYNC,
        source_date=source_date,
        holidays=tuple(holidays),
    )


def fetch_gov_uk_calendar(
    *,
    source_date: date,
    timeout_seconds: float = 10.0,
) -> PublicHolidayCalendar:
    """Download and parse the official calendar.

    Calling code should catch network errors and retain the existing
    cached or built-in snapshot.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    request = Request(
        GOV_UK_BANK_HOLIDAYS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "LeavePlanner/0.1",
        },
    )

    with urlopen(
        request,
        timeout=timeout_seconds,
    ) as response:
        payload = response.read(_MAX_RESPONSE_BYTES + 1)

    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError("GOV.UK response exceeded the size limit")

    return parse_gov_uk_calendar(
        payload,
        source_date=source_date,
    )

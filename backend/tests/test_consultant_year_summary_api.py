"""Workbook-facing integration tests for the consultant-year summary."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reference_cases.workbook import WORKBOOK_LEAVE_ROWS

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    return create_app(
        settings=Settings(environment="test", data_dir=data_dir),
        frontend_dist=data_dir / "no-frontend-build",
    )


def job_plan(effective_from: str, effective_until: str) -> dict[str, Any]:
    visible = {0: ("8", "0.5"), 1: ("8", "2"), 2: ("4.5", "1.5")}
    return {
        "effective_from": effective_from,
        "effective_until": effective_until,
        "cycle_anchor_date": None,
        "week_count": 1,
        "contracted_pas": "8.47",
        "dcc_pas": "5.91",
        "spa_pas": "2.56",
        "other_pas": "0",
        "hours_per_pa": "4",
        "additional_dcc_hours": "3",
        "additional_spa_hours": "4",
        "reconciliation_override_reason": None,
        "days": [
            {
                "cycle_week": 1,
                "weekday": weekday,
                "dcc_hours": visible.get(weekday, ("0", "0"))[0],
                "spa_hours": visible.get(weekday, ("0", "0"))[1],
                "other_hours": "0",
            }
            for weekday in range(7)
        ],
    }


def synthetic_job_plan(
    effective_from: str,
    effective_until: str,
    *,
    contracted_pas: str,
    dcc_pas: str,
    spa_pas: str,
    week_count: int,
    pattern: dict[tuple[int, int], tuple[str, str]],
) -> dict[str, Any]:
    return {
        "effective_from": effective_from,
        "effective_until": effective_until,
        "cycle_anchor_date": "2025-12-29" if week_count > 1 else None,
        "week_count": week_count,
        "contracted_pas": contracted_pas,
        "dcc_pas": dcc_pas,
        "spa_pas": spa_pas,
        "other_pas": "0",
        "hours_per_pa": "4",
        "additional_dcc_hours": "0",
        "additional_spa_hours": "0",
        "reconciliation_override_reason": None,
        "days": [
            {
                "cycle_week": week,
                "weekday": weekday,
                "dcc_hours": pattern.get((week, weekday), ("0", "0"))[0],
                "spa_hours": pattern.get((week, weekday), ("0", "0"))[1],
                "other_hours": "0",
            }
            for week in range(1, week_count + 1)
            for weekday in range(7)
        ],
    }


def test_summary_reconciles_the_workbook_periods_and_actual_balance(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant = client.post(
            "/api/consultants",
            json={"name": "Anonymous", "post_title": "Consultant in Radiology"},
        ).json()
        consultant_id = int(consultant["id"])
        year = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={"start_date": "2025-08-29", "end_date": "2026-08-28"},
        ).json()
        year_id = int(year["id"])
        root = f"/api/consultants/{consultant_id}/leave-years/{year_id}"

        assert client.post(
            f"{root}/job-plans", json=job_plan("2025-08-29", "2026-08-01")
        ).status_code == 201
        assert client.post(
            f"{root}/job-plans", json=job_plan("2026-08-01", "2026-08-29")
        ).status_code == 201
        assert client.put(
            f"{root}/entitlement",
            json={
                "mode": "calculated",
                "consultant_appointment_date": "2010-01-01",
                "consultant_service_start_date": "2010-01-01",
                "other_hours": "0",
            },
        ).status_code == 200
        assert client.put(f"{root}/carry-forward", json={"hours": "41.25"}).status_code == 200
        assert client.put(
            f"{root}/public-holidays/2026-05-04/treatment",
            json={"basis": "qualifying_on_call", "note": "Workbook on-call entry"},
        ).status_code == 200

        # Each entered row is saved as a historical daily replacement, exactly
        # as the workbook records DCC and SPA leave independently.
        for leave_date, dcc, spa in WORKBOOK_LEAVE_ROWS:
            iso_date = leave_date.isoformat()
            response = client.post(
                f"{root}/bookings",
                json={
                    "start_date": iso_date,
                    "end_date": iso_date,
                    "state": "taken",
                    "note": "Workbook reference",
                    "overrides": [
                        {
                            "leave_date": iso_date,
                            "dcc_hours": dcc,
                            "spa_hours": spa,
                        }
                    ],
                },
            )
            assert response.status_code == 201

        response = client.get(f"{root}/summary")
        assert response.status_code == 200
        summary = response.json()

    assert summary["consultant"]["name"] == "Anonymous"
    assert summary["allocation_source"] == "recommendation"
    assert [period["calendar_days"] for period in summary["job_plan_periods"]] == [337, 28]
    assert [Decimal(period["standard_dcc_hours"]) for period in summary["job_plan_periods"]] == [
        Decimal("23.5"),
        Decimal("23.5"),
    ]
    assert [Decimal(period["standard_spa_hours"]) for period in summary["job_plan_periods"]] == [
        Decimal("8"),
        Decimal("8"),
    ]
    assert sum(
        Decimal(period["gross_entitlement_hours"])
        for period in summary["job_plan_periods"]
    ) == Decimal("291.368")
    actual = summary["balances"]["actual"]
    assert Decimal(actual["used"]["dcc_hours"]) == Decimal("229.5")
    assert Decimal(actual["used"]["spa_hours"]) == Decimal("18")
    assert Decimal(actual["remaining"]["dcc_hours"]).quantize(Decimal("0.001")) == Decimal(
        "15.054"
    )
    assert Decimal(actual["remaining"]["spa_hours"]).quantize(Decimal("0.001")) == Decimal(
        "70.064"
    )
    assert summary["weekday_counts"] == {
        "monday": 14,
        "tuesday": 12,
        "wednesday": 12,
        "thursday": 2,
        "friday": 2,
    }
    assert len(summary["planning"]["bookings"]) == len(WORKBOOK_LEAVE_ROWS)
    assert summary["audit_events"][0]["entity_type"] == "leave_booking"


def test_summary_remains_available_before_a_job_plan_is_added(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        consultant_id = client.post(
            "/api/consultants", json={"name": "Setup Consultant", "post_title": None}
        ).json()["id"]
        year_id = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        ).json()["id"]
        response = client.get(
            f"/api/consultants/{consultant_id}/leave-years/{year_id}/summary"
        )

    assert response.status_code == 200
    assert response.json()["job_plan_periods"] == []
    assert response.json()["balances"]["actual"] is None
    assert response.json()["warnings"][0]["code"] == "job-plan.required"


@pytest.mark.parametrize(
    ("name", "plans", "expected_periods", "expected_pas"),
    [
        (
            "Full Time",
            (
                synthetic_job_plan(
                    "2026-01-01",
                    "2027-01-01",
                    contracted_pas="10",
                    dcc_pas="8",
                    spa_pas="2",
                    week_count=1,
                    pattern={(1, weekday): ("8", "0") for weekday in range(5)},
                ),
            ),
            1,
            "10",
        ),
        (
            "LTFT Uneven",
            (
                synthetic_job_plan(
                    "2026-01-01",
                    "2027-01-01",
                    contracted_pas="6",
                    dcc_pas="4.5",
                    spa_pas="1.5",
                    week_count=1,
                    pattern={(1, 0): ("12", "0"), (1, 1): ("6", "6")},
                ),
            ),
            1,
            "6",
        ),
        (
            "Capped Multiweek",
            (
                synthetic_job_plan(
                    "2026-01-01",
                    "2026-10-01",
                    contracted_pas="12",
                    dcc_pas="9",
                    spa_pas="3",
                    week_count=2,
                    pattern={(1, 0): ("8", "4"), (2, 0): ("12", "0")},
                ),
                synthetic_job_plan(
                    "2026-10-01",
                    "2027-01-01",
                    contracted_pas="12",
                    dcc_pas="8",
                    spa_pas="4",
                    week_count=2,
                    pattern={(1, 3): ("8", "4"), (2, 3): ("12", "0")},
                ),
            ),
            2,
            "12",
        ),
    ],
)
def test_summary_api_supports_reference_shapes(
    tmp_path: Path,
    name: str,
    plans: tuple[dict[str, Any], ...],
    expected_periods: int,
    expected_pas: str,
) -> None:
    """Exercise the three maintained reference shapes through the public API."""

    with TestClient(app_for(tmp_path)) as client:
        consultant_id = client.post(
            "/api/consultants", json={"name": name, "post_title": "Consultant"}
        ).json()["id"]
        year_id = client.post(
            f"/api/consultants/{consultant_id}/leave-years",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        ).json()["id"]
        root = f"/api/consultants/{consultant_id}/leave-years/{year_id}"
        for plan in plans:
            response = client.post(f"{root}/job-plans", json=plan)
            assert response.status_code == 201, response.text
        assert client.put(
            f"{root}/entitlement",
            json={
                "mode": "calculated",
                "consultant_appointment_date": "2019-07-01",
                "consultant_service_start_date": "2019-07-01",
                "other_hours": "0",
            },
        ).status_code == 200
        summary = client.get(f"{root}/summary")

    assert summary.status_code == 200
    payload = summary.json()
    assert len(payload["job_plan_periods"]) == expected_periods
    assert all(
        Decimal(period["contracted_pas"]) == Decimal(expected_pas)
        for period in payload["job_plan_periods"]
    )
    assert payload["entitlement"]["recommendation"] is not None
    assert payload["balances"]["actual"] is not None

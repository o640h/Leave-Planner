"""Simplify annual-entitlement selection.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-18
"""

import json
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _as_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _completed_years(service_start: date, calculation_date: date) -> int:
    years = calculation_date.year - service_start.year
    if (calculation_date.month, calculation_date.day) < (
        service_start.month,
        service_start.day,
    ):
        years -= 1
    return max(years, 0)


def _service_reference(active_start: date, seven_years_or_more: bool) -> date:
    if not seven_years_or_more:
        return active_start
    try:
        return active_start.replace(year=active_start.year - 7)
    except ValueError:
        return active_start.replace(year=active_start.year - 7, day=28)


def upgrade() -> None:
    connection = op.get_bind()
    rows = tuple(
        connection.execute(
            sa.text(
                """
            SELECT entitlement_recommendations.id,
                   entitlement_recommendations.inputs_json,
                   leave_years.start_date,
                   leave_years.employment_start
            FROM entitlement_recommendations
            JOIN leave_years
              ON leave_years.id = entitlement_recommendations.leave_year_id
                """
            )
        ).mappings()
    )

    for row in rows:
        inputs = json.loads(row["inputs_json"])
        service_start_text = inputs.pop("consultant_service_start_date", None)
        inputs.pop("consultant_appointment_date", None)
        if "seven_years_or_more" not in inputs:
            active_start = _as_date(row["employment_start"] or row["start_date"])
            service_start = (
                date.fromisoformat(service_start_text) if service_start_text else active_start
            )
            inputs["seven_years_or_more"] = (
                _completed_years(
                    service_start,
                    active_start,
                )
                >= 7
            )
        connection.execute(
            sa.text(
                "UPDATE entitlement_recommendations "
                "SET inputs_json = :inputs_json WHERE id = :recommendation_id"
            ),
            {
                "inputs_json": json.dumps(inputs, sort_keys=True),
                "recommendation_id": row["id"],
            },
        )

    connection.execute(
        sa.text(
            "UPDATE applied_entitlements "
            "SET mode = 'manual' WHERE mode = 'calculated_with_override'"
        )
    )
    with op.batch_alter_table("applied_entitlements") as batch:
        batch.drop_constraint("ck_applied_entitlement_mode", type_="check")
        batch.create_check_constraint(
            "ck_applied_entitlement_mode",
            "mode IN ('calculated', 'manual')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    rows = tuple(
        connection.execute(
            sa.text(
                """
            SELECT entitlement_recommendations.id,
                   entitlement_recommendations.inputs_json,
                   leave_years.start_date,
                   leave_years.employment_start
            FROM entitlement_recommendations
            JOIN leave_years
              ON leave_years.id = entitlement_recommendations.leave_year_id
                """
            )
        ).mappings()
    )

    for row in rows:
        inputs = json.loads(row["inputs_json"])
        seven_years_or_more = bool(inputs.pop("seven_years_or_more", False))
        active_start = _as_date(row["employment_start"] or row["start_date"])
        inputs["consultant_appointment_date"] = "2005-04-01"
        inputs["consultant_service_start_date"] = _service_reference(
            active_start,
            seven_years_or_more,
        ).isoformat()
        connection.execute(
            sa.text(
                "UPDATE entitlement_recommendations "
                "SET inputs_json = :inputs_json WHERE id = :recommendation_id"
            ),
            {
                "inputs_json": json.dumps(inputs, sort_keys=True),
                "recommendation_id": row["id"],
            },
        )

    with op.batch_alter_table("applied_entitlements") as batch:
        batch.drop_constraint("ck_applied_entitlement_mode", type_="check")
        batch.create_check_constraint(
            "ck_applied_entitlement_mode",
            "mode IN ('calculated', 'calculated_with_override', 'manual')",
        )

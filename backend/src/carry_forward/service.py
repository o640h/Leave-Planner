"""Consultant-year carry-forward persistence."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import record_audit_event
from leave_years import service as leave_year_service

from .persistence import CarryForwardRecord
from .schemas import CarryForwardRead, CarryForwardWrite


def _records(session: Session, leave_year_id: int) -> tuple[CarryForwardRecord, ...]:
    return tuple(
        session.scalars(
            select(CarryForwardRecord).where(
                CarryForwardRecord.leave_year_id == leave_year_id,
                CarryForwardRecord.kind == "carry_forward",
            )
        )
    )


def get_carry_forward(session: Session, consultant_id: int, leave_year_id: int) -> CarryForwardRead:
    leave_year_service.get_leave_year(session, consultant_id, leave_year_id)
    records = _records(session, leave_year_id)
    return CarryForwardRead(
        id=records[-1].id if records else None,
        leave_year_id=leave_year_id,
        dcc_hours=sum((record.dcc_hours for record in records), Decimal("0")),
        spa_hours=sum((record.spa_hours for record in records), Decimal("0")),
        total_hours=sum(
            (record.dcc_hours + record.spa_hours for record in records), Decimal("0")
        ),
        created_at=records[-1].created_at if records else None,
    )


def set_carry_forward(
    session: Session,
    consultant_id: int,
    leave_year_id: int,
    details: CarryForwardWrite,
) -> CarryForwardRead:
    before = get_carry_forward(session, consultant_id, leave_year_id)
    for record in _records(session, leave_year_id):
        session.delete(record)
    session.flush()

    record_id = before.id
    if details.dcc_hours > 0 or details.spa_hours > 0:
        record = CarryForwardRecord(
            leave_year_id=leave_year_id,
            kind="carry_forward",
            dcc_hours=details.dcc_hours,
            spa_hours=details.spa_hours,
            other_hours=Decimal("0"),
            reason="Carry forward from previous leave year",
            source=None,
        )
        session.add(record)
        session.flush()
        record_id = record.id

    record_audit_event(
        session,
        consultant_id=consultant_id,
        entity_type="carry_forward",
        entity_id=record_id or leave_year_id,
        action="updated",
        details={
            "before": {
                "dcc_hours": str(before.dcc_hours),
                "spa_hours": str(before.spa_hours),
            },
            "after": {
                "dcc_hours": str(details.dcc_hours),
                "spa_hours": str(details.spa_hours),
            },
        },
    )
    return get_carry_forward(session, consultant_id, leave_year_id)

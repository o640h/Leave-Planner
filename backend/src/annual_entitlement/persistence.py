"""Stored entitlement recommendations and applied opening values."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class EntitlementRecommendationRecord(Base):
    """An immutable snapshot of one calculated recommendation."""

    __tablename__ = "entitlement_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    trace_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        nullable=False,
    )


class AppliedEntitlementRecord(Base):
    """The operator-approved opening entitlement for one leave year."""

    __tablename__ = "applied_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "leave_year_id",
            name="uq_applied_entitlement_leave_year",
        ),
        CheckConstraint(
            """
            mode IN (
                'calculated',
                'manual'
            )
            """,
            name="ck_applied_entitlement_mode",
        ),
        CheckConstraint(
            "dcc_hours >= 0",
            name="ck_applied_entitlement_dcc_hours",
        ),
        CheckConstraint(
            "spa_hours >= 0",
            name="ck_applied_entitlement_spa_hours",
        ),
        CheckConstraint(
            "other_hours >= 0",
            name="ck_applied_entitlement_other_hours",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_year_id: Mapped[int] = mapped_column(
        ForeignKey("leave_years.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "entitlement_recommendations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    dcc_hours: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )
    spa_hours: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )
    other_hours: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

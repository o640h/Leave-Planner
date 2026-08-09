"""Persisted consultant records."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Consultant(Base):
    """One consultant maintained in the central directory."""

    __tablename__ = "consultants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    post_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(),
        nullable=True,
        index=True,
    )

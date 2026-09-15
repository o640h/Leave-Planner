"""Persisted consultant records."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Consultant(Base):
    """One consultant maintained in the central directory."""

    __tablename__ = "consultants"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_consultants_workspace_id_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    post_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(),
        nullable=True,
        index=True,
    )

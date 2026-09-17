"""API contracts for the read-only policy library."""

from datetime import date

from pydantic import BaseModel


class PolicyDocumentRead(BaseModel):
    """Public metadata for one downloadable policy document."""

    document_id: str
    document_type: str
    title: str
    version: str
    effective_date: date
    filename: str

"""Shared contracts for deliberate removal workflows."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

EntitlementRemovalStatus = Literal[
    "not_applicable",
    "not_configured",
    "preserved",
    "refreshed",
    "needs_attention",
]


class RemovalImpact(BaseModel):
    """Consequences shown before an operator confirms a removal."""

    model_config = ConfigDict(from_attributes=True)

    resource_name: str
    action: Literal["archive", "delete"]
    confirmation_text: str
    consequences: tuple[str, ...]
    can_proceed: bool = True
    blocking_reason: str | None = None


class RemovalCommand(BaseModel):
    """Explicit text confirmation submitted by the operator."""

    confirmation: str


class RemovalResult(BaseModel):
    """Outcome returned after a removal completes."""

    message: str
    entitlement_status: EntitlementRemovalStatus = "not_applicable"

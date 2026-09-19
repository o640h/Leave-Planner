"""Privacy-limited email notifications for Member leave request activity."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from authentication.account_actions import deliver_message
from authentication.email_delivery import EmailMessage, EmailSender
from authentication.models import ACTIVE, User
from workspaces.models import ADMIN_ROLE, OWNER_ROLE, Workspace, WorkspaceMembership

REVIEW_NOTIFICATION = "leave_request_review"
DECISION_NOTIFICATION = "leave_request_decision"

OperatorEvent = Literal["submitted", "withdrawn", "cancellation_requested"]
MemberDecision = Literal[
    "approved",
    "rejected",
    "cancellation_approved",
    "cancellation_rejected",
]


def _workspace_name(session: Session, workspace_id: int) -> str:
    name = session.scalar(select(Workspace.name).where(Workspace.id == workspace_id))
    return name or "Your Workspace"


def _operator_addresses(session: Session, workspace_id: int) -> tuple[str, ...]:
    return tuple(
        session.scalars(
            select(User.display_email)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role.in_((OWNER_ROLE, ADMIN_ROLE)),
                User.security_state == ACTIVE,
                User.email_verified_at.is_not(None),
            )
            .order_by(User.id)
        )
    )


def _member_address(session: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return session.scalar(
        select(User.display_email).where(
            User.id == user_id,
            User.security_state == ACTIVE,
            User.email_verified_at.is_not(None),
        )
    )


def _operator_message(
    recipient: str,
    workspace_name: str,
    origin: str,
    event: OperatorEvent,
) -> EmailMessage:
    copy = {
        "submitted": (
            "Leave Request Ready For Review",
            "A Member submitted a leave request for review.",
        ),
        "withdrawn": (
            "Leave Request Withdrawn",
            "A Member withdrew a pending leave request.",
        ),
        "cancellation_requested": (
            "Leave Cancellation Ready For Review",
            "A Member submitted an Approved booking cancellation for review.",
        ),
    }
    subject, summary = copy[event]
    return EmailMessage(
        recipient=recipient,
        subject=subject,
        text=(
            f"{summary}\n\nWorkspace: {workspace_name}\n\n"
            f"Sign in to Leave Planner: {origin.rstrip('/')}"
        ),
    )


def _member_message(
    recipient: str,
    workspace_name: str,
    origin: str,
    decision: MemberDecision,
) -> EmailMessage:
    copy = {
        "approved": (
            "Leave Request Approved",
            "Your leave request was approved.",
        ),
        "rejected": (
            "Leave Request Not Approved",
            "Your leave request was not approved.",
        ),
        "cancellation_approved": (
            "Leave Cancellation Approved",
            "Your request to cancel Approved leave was approved.",
        ),
        "cancellation_rejected": (
            "Leave Cancellation Not Approved",
            "Your request to cancel Approved leave was not approved. The booking remains Approved.",
        ),
    }
    subject, summary = copy[decision]
    return EmailMessage(
        recipient=recipient,
        subject=subject,
        text=(
            f"{summary}\n\nWorkspace: {workspace_name}\n\n"
            f"Sign in to Leave Planner: {origin.rstrip('/')}"
        ),
    )


def notify_operators(
    session: Session,
    sender: EmailSender,
    *,
    workspace_id: int,
    origin: str,
    event: OperatorEvent,
) -> None:
    """Tell active Owners and Admins about one Member request event."""

    workspace_name = _workspace_name(session, workspace_id)
    for recipient in _operator_addresses(session, workspace_id):
        deliver_message(
            session,
            sender,
            purpose=REVIEW_NOTIFICATION,
            message=_operator_message(recipient, workspace_name, origin, event),
            action_token_id=None,
        )


def notify_member(
    session: Session,
    sender: EmailSender,
    *,
    workspace_id: int,
    requester_user_id: int | None,
    origin: str,
    decision: MemberDecision,
) -> None:
    """Tell the exact requesting Member about a completed review decision."""

    recipient = _member_address(session, requester_user_id)
    if recipient is None:
        return
    deliver_message(
        session,
        sender,
        purpose=DECISION_NOTIFICATION,
        message=_member_message(
            recipient,
            _workspace_name(session, workspace_id),
            origin,
            decision,
        ),
        action_token_id=None,
    )

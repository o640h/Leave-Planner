"""Single-use email verification, recovery, invitation, and email-change proofs."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .email_delivery import EmailDeliveryError, EmailMessage, EmailSender
from .models import (
    ACCOUNT_ACTION_PURPOSES,
    EMAIL_CHANGE,
    EMAIL_VERIFICATION,
    INVITATION,
    PASSWORD_RESET,
    AccountActionToken,
    EmailDeliveryAttempt,
)
from .service import token_hash

VERIFICATION_LIFETIME = timedelta(hours=24)
EMAIL_CHANGE_LIFETIME = timedelta(hours=24)
PASSWORD_RESET_LIFETIME = timedelta(hours=1)
INVITATION_LIFETIME = timedelta(days=7)


@dataclass(frozen=True)
class IssuedAction:
    record: AccountActionToken
    raw_token: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def comparable_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def issue_action(
    session: Session,
    *,
    purpose: str,
    canonical_email: str,
    display_email: str,
    lifetime: timedelta,
    user_id: int | None,
    workspace_id: int | None = None,
    now: datetime | None = None,
) -> IssuedAction:
    if purpose not in ACCOUNT_ACTION_PURPOSES:
        raise ValueError("Unsupported account action purpose")
    if purpose != INVITATION and user_id is None:
        raise ValueError("This account action requires a user")
    moment = now or utc_now()
    statement = update(AccountActionToken).where(
        AccountActionToken.purpose == purpose,
        AccountActionToken.canonical_email == canonical_email,
        AccountActionToken.consumed_at.is_(None),
        AccountActionToken.revoked_at.is_(None),
    )
    if user_id is None:
        statement = statement.where(AccountActionToken.user_id.is_(None))
    else:
        statement = statement.where(AccountActionToken.user_id == user_id)
    if workspace_id is None:
        statement = statement.where(AccountActionToken.workspace_id.is_(None))
    else:
        statement = statement.where(AccountActionToken.workspace_id == workspace_id)
    session.execute(statement.values(revoked_at=moment))

    raw_token = secrets.token_urlsafe(32)
    record = AccountActionToken(
        user_id=user_id,
        workspace_id=workspace_id,
        purpose=purpose,
        token_hash=token_hash(raw_token),
        canonical_email=canonical_email,
        display_email=display_email,
        created_at=moment,
        expires_at=moment + lifetime,
    )
    session.add(record)
    session.flush()
    return IssuedAction(record=record, raw_token=raw_token)


def valid_action(
    session: Session,
    *,
    purpose: str,
    raw_token: str,
    now: datetime | None = None,
    for_update: bool = True,
) -> AccountActionToken | None:
    statement = select(AccountActionToken).where(
        AccountActionToken.purpose == purpose,
        AccountActionToken.token_hash == token_hash(raw_token),
        AccountActionToken.consumed_at.is_(None),
        AccountActionToken.revoked_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    record = session.scalar(statement)
    if record is None:
        return None
    moment = now or utc_now()
    if comparable_datetime(record.expires_at) <= moment:
        return None
    return record


def consume_action(record: AccountActionToken, *, now: datetime | None = None) -> None:
    record.consumed_at = now or utc_now()


def revoke_user_actions(session: Session, user_id: int, *, now: datetime | None = None) -> None:
    session.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user_id,
            AccountActionToken.consumed_at.is_(None),
            AccountActionToken.revoked_at.is_(None),
        )
        .values(revoked_at=now or utc_now())
    )


def recipient_hint(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "redacted"
    visible = local[:1] if local else "*"
    return f"{visible}***@{domain}"


def action_link(origin: str, action: str, raw_token: str) -> str:
    return f"{origin.rstrip('/')}/?{urlencode({'action': action, 'token': raw_token})}"


def deliver_message(
    session: Session,
    sender: EmailSender,
    *,
    purpose: str,
    message: EmailMessage,
    action_token_id: int | None,
) -> EmailDeliveryAttempt:
    attempt = EmailDeliveryAttempt(
        action_token_id=action_token_id,
        purpose=purpose,
        recipient_hint=recipient_hint(message.recipient),
        idempotency_key=f"{purpose}/{uuid.uuid4().hex}",
        status="pending",
        created_at=utc_now(),
    )
    session.add(attempt)
    session.flush()
    try:
        attempt.provider_message_id = sender.send(
            message,
            idempotency_key=attempt.idempotency_key,
        )
    except EmailDeliveryError as error:
        attempt.status = "failed"
        attempt.failure_code = error.code
    else:
        attempt.status = "sent"
    attempt.completed_at = utc_now()
    return attempt


def verification_message(email: str, link: str) -> EmailMessage:
    return EmailMessage(
        recipient=email,
        subject="Verify Your Leave Planner Email",
        text=(
            "Confirm your email address to finish securing your Leave Planner account.\n\n"
            f"{link}\n\nThis link expires in 24 hours and can be used once."
        ),
    )


def password_reset_message(email: str, link: str) -> EmailMessage:
    return EmailMessage(
        recipient=email,
        subject="Reset Your Leave Planner Password",
        text=(
            "A password reset was requested for your Leave Planner account.\n\n"
            f"{link}\n\nThis link expires in one hour and can be used once. "
            "If you did not request this, you can ignore this message."
        ),
    )


def email_change_message(email: str, link: str) -> EmailMessage:
    return EmailMessage(
        recipient=email,
        subject="Confirm Your New Leave Planner Email",
        text=(
            "Confirm this address as the new email for your Leave Planner account.\n\n"
            f"{link}\n\nThis link expires in 24 hours and can be used once."
        ),
    )


def email_changed_notice(email: str) -> EmailMessage:
    return EmailMessage(
        recipient=email,
        subject="Your Leave Planner Email Was Changed",
        text=(
            "The sign-in email for your Leave Planner account was changed. "
            "If you did not make this change, contact the deployment operator immediately."
        ),
    )


__all__ = [
    "EMAIL_CHANGE",
    "EMAIL_CHANGE_LIFETIME",
    "EMAIL_VERIFICATION",
    "INVITATION",
    "INVITATION_LIFETIME",
    "PASSWORD_RESET",
    "PASSWORD_RESET_LIFETIME",
    "VERIFICATION_LIFETIME",
    "IssuedAction",
    "action_link",
    "consume_action",
    "deliver_message",
    "email_change_message",
    "email_changed_notice",
    "issue_action",
    "password_reset_message",
    "revoke_user_actions",
    "valid_action",
    "verification_message",
]

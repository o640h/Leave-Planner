"""Email authentication, account state, and session lifecycle rules."""

import hashlib
import json
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    ACTIVE,
    DELETED,
    DISABLED,
    PENDING_VERIFICATION,
    SecurityEvent,
    User,
    UserSession,
)
from .passwords import DUMMY_PASSWORD_HASH, hash_password, verify_password

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@dataclass(frozen=True)
class EmailIdentity:
    canonical: str
    display: str


@dataclass(frozen=True)
class SessionTokens:
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    public_id: str
    display_name: str
    display_email: str
    session_id: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalise_email(value: str) -> EmailIdentity:
    display = value.strip()
    try:
        result = validate_email(display, check_deliverability=False)
    except EmailNotValidError as error:
        raise ValueError("Enter a valid email address") from error
    return EmailIdentity(canonical=result.normalized.casefold(), display=display)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comparable_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def account_for_email(session: Session, email: str, *, for_update: bool = False) -> User | None:
    identity = normalise_email(email)
    statement = select(User).where(User.canonical_email == identity.canonical)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_account(
    session: Session,
    *,
    display_name: str,
    email: str,
    password: str,
    verified_at: datetime | None = None,
) -> User:
    name = display_name.strip()
    if not name:
        raise ValueError("Enter a display name")
    identity = normalise_email(email)
    if (
        session.scalar(select(User.id).where(User.canonical_email == identity.canonical))
        is not None
    ):
        raise ValueError("An account already uses this email address")
    moment = utc_now()
    account = User(
        public_id=uuid.uuid4().hex,
        display_name=name,
        canonical_email=identity.canonical,
        display_email=identity.display,
        email_verified_at=verified_at,
        security_state=ACTIVE if verified_at is not None else PENDING_VERIFICATION,
        password_hash=hash_password(password),
        password_version=1,
        failed_login_count=0,
        created_at=moment,
        password_changed_at=moment,
    )
    session.add(account)
    session.flush()
    record_security_event(
        session,
        "account_created",
        user_id=account.id,
        actor_label="Server Owner",
        details={"verified": verified_at is not None},
    )
    return account


def password_is_valid(user: User | None, password: str) -> bool:
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    verified = verify_password(stored_hash, password)
    return bool(
        user is not None
        and user.security_state == ACTIVE
        and user.email_verified_at is not None
        and verified
    )


def lockout_remaining_seconds(user: User, *, now: datetime | None = None) -> int:
    if user.locked_until is None:
        return 0
    moment = now or utc_now()
    remaining = (comparable_datetime(user.locked_until) - moment).total_seconds()
    if remaining <= 0:
        user.failed_login_count = 0
        user.locked_until = None
        return 0
    return math.ceil(remaining)


def record_failed_login(user: User, *, now: datetime | None = None) -> None:
    moment = now or utc_now()
    user.failed_login_count += 1
    if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
        user.locked_until = moment + LOCKOUT_DURATION


def clear_failed_logins(user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None


def record_security_event(
    session: Session,
    event_type: str,
    *,
    user_id: int | None,
    actor_label: str,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            actor_label=actor_label,
            details=json.dumps(details or {}, sort_keys=True),
        )
    )


def create_session(
    session: Session,
    user: User,
    *,
    lifetime: timedelta,
    now: datetime | None = None,
) -> SessionTokens:
    moment = now or utc_now()
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash(session_token),
            csrf_token_hash=token_hash(csrf_token),
            password_version=user.password_version,
            created_at=moment,
            last_seen_at=moment,
            expires_at=moment + lifetime,
        )
    )
    record_security_event(
        session,
        "login_succeeded",
        user_id=user.id,
        actor_label=user.display_name,
        details={"source": "http"},
    )
    return SessionTokens(session_token=session_token, csrf_token=csrf_token)


def authenticated_user(
    session: Session,
    raw_token: str | None,
    *,
    now: datetime | None = None,
) -> AuthenticatedUser | None:
    if not raw_token:
        return None
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_hash(raw_token))
    ).one_or_none()
    if row is None:
        return None

    stored_session, user = row
    moment = now or utc_now()
    if (
        stored_session.revoked_at is not None
        or comparable_datetime(stored_session.expires_at) <= moment
        or user.security_state != ACTIVE
        or user.email_verified_at is None
        or stored_session.password_version != user.password_version
    ):
        return None

    stored_session.last_seen_at = moment
    return AuthenticatedUser(
        id=user.id,
        public_id=user.public_id,
        display_name=user.display_name,
        display_email=user.display_email,
        session_id=stored_session.id,
    )


def csrf_is_valid(session: Session, session_id: int, raw_csrf_token: str | None) -> bool:
    if not raw_csrf_token:
        return False
    stored_hash = session.scalar(
        select(UserSession.csrf_token_hash).where(UserSession.id == session_id)
    )
    return bool(stored_hash and secrets.compare_digest(stored_hash, token_hash(raw_csrf_token)))


def revoke_session(
    session: Session,
    authenticated: AuthenticatedUser,
    *,
    now: datetime | None = None,
) -> None:
    moment = now or utc_now()
    session.execute(
        update(UserSession)
        .where(UserSession.id == authenticated.session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=moment)
    )
    record_security_event(
        session,
        "logout",
        user_id=authenticated.id,
        actor_label=authenticated.display_name,
        details={"source": "http"},
    )


def revoke_all_sessions(session: Session, user_id: int, *, now: datetime) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def reset_account_password(session: Session, account: User, password: str) -> None:
    moment = utc_now()
    account.password_hash = hash_password(password)
    account.password_version += 1
    account.password_changed_at = moment
    clear_failed_logins(account)
    revoke_all_sessions(session, account.id, now=moment)
    record_security_event(session, "password_reset", user_id=account.id, actor_label="Server Owner")


def set_account_state(session: Session, account: User, state: str) -> None:
    if state not in {ACTIVE, DISABLED, DELETED}:
        raise ValueError("Unsupported account state")
    if state == ACTIVE and account.email_verified_at is None:
        raise ValueError("An account must have a verified email before it can be enabled")
    moment = utc_now()
    account.security_state = state
    account.disabled_at = moment if state in {DISABLED, DELETED} else None
    clear_failed_logins(account)
    if state != ACTIVE:
        revoke_all_sessions(session, account.id, now=moment)
    record_security_event(
        session,
        f"account_{state}",
        user_id=account.id,
        actor_label="Server Owner",
    )

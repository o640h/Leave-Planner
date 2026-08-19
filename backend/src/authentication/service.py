"""Authentication, account administration, and session lifecycle rules."""

import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import SecurityEvent, User, UserSession
from .passwords import DUMMY_PASSWORD_HASH, hash_password, verify_password

ADMIN_NAME = "Admin"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@dataclass(frozen=True)
class SessionTokens:
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    display_name: str
    session_id: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comparable_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def admin_user(session: Session, *, for_update: bool = False) -> User | None:
    statement = select(User).where(User.display_name == ADMIN_NAME)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def password_is_valid(user: User | None, password: str) -> bool:
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    verified = verify_password(stored_hash, password)
    return bool(user is not None and user.enabled and verified)


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


def record_failed_login(user: User, *, now: datetime | None = None) -> int:
    moment = now or utc_now()
    user.failed_login_count += 1
    if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
        user.locked_until = moment + LOCKOUT_DURATION
        return int(LOCKOUT_DURATION.total_seconds())
    return 0


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

    statement = (
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_hash(raw_token))
    )
    row = session.execute(statement).one_or_none()
    if row is None:
        return None

    stored_session, user = row
    moment = now or utc_now()
    if (
        stored_session.revoked_at is not None
        or comparable_datetime(stored_session.expires_at) <= moment
        or not user.enabled
        or stored_session.password_version != user.password_version
    ):
        return None

    stored_session.last_seen_at = moment
    return AuthenticatedUser(
        id=user.id,
        display_name=user.display_name,
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


def create_admin(session: Session, password: str) -> User:
    if admin_user(session) is not None:
        raise ValueError("Admin already exists; use reset-password instead")
    moment = utc_now()
    user = User(
        display_name=ADMIN_NAME,
        password_hash=hash_password(password),
        enabled=True,
        password_version=1,
        failed_login_count=0,
        created_at=moment,
        password_changed_at=moment,
    )
    session.add(user)
    session.flush()
    from workspaces.service import ensure_initial_membership

    ensure_initial_membership(session, user)
    record_security_event(session, "account_created", user_id=user.id, actor_label="Server Owner")
    return user


def reset_admin_password(session: Session, password: str) -> User:
    user = require_admin(session)
    moment = utc_now()
    user.password_hash = hash_password(password)
    user.password_version += 1
    user.password_changed_at = moment
    clear_failed_logins(user)
    revoke_all_sessions(session, user.id, now=moment)
    record_security_event(session, "password_reset", user_id=user.id, actor_label="Server Owner")
    return user


def set_admin_enabled(session: Session, *, enabled: bool) -> User:
    user = require_admin(session)
    moment = utc_now()
    user.enabled = enabled
    user.disabled_at = None if enabled else moment
    clear_failed_logins(user)
    if not enabled:
        revoke_all_sessions(session, user.id, now=moment)
    record_security_event(
        session,
        "account_enabled" if enabled else "account_disabled",
        user_id=user.id,
        actor_label="Server Owner",
    )
    return user


def require_admin(session: Session) -> User:
    user = admin_user(session)
    if user is None:
        raise ValueError("Admin has not been created")
    return user

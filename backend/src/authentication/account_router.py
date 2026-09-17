"""Email verification, password recovery, and email-change endpoints."""

from datetime import timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from dependencies import DatabaseSession
from errors import ApiError
from workspaces.management import accept_claimed_invitations, claim_invitation_for_registration

from .account_actions import (
    EMAIL_CHANGE,
    EMAIL_CHANGE_LIFETIME,
    EMAIL_VERIFICATION,
    PASSWORD_RESET,
    PASSWORD_RESET_LIFETIME,
    VERIFICATION_LIFETIME,
    action_link,
    consume_action,
    deliver_message,
    email_change_message,
    email_changed_notice,
    issue_action,
    password_reset_message,
    revoke_user_actions,
    valid_action,
    verification_message,
)
from .dependencies import (
    require_authenticated_request,
    runtime_settings,
    validate_request_origin,
)
from .email_delivery import DevelopmentOutbox, EmailMessage, EmailSender
from .models import ACTIVE, PENDING_VERIFICATION, User
from .schemas import (
    DevelopmentEmailRead,
    EmailActionRequest,
    EmailChangeRequest,
    MessageRead,
    PasswordChangeRequest,
    PasswordResetRequest,
    RegistrationConfigurationRead,
    RegistrationRequest,
    TokenRequest,
)
from .service import (
    AuthenticatedUser,
    account_for_email,
    change_account_password,
    create_account,
    normalise_email,
    password_matches,
    reauthenticate_session,
    record_security_event,
    reset_account_password,
    revoke_all_sessions,
    session_was_recently_reauthenticated,
    utc_now,
)

router = APIRouter(prefix="/api/auth", tags=["account recovery"])
GENERIC_REQUEST_MESSAGE = (
    "If the address can use this action, an email will arrive with the next step."
)
INVALID_TOKEN_MESSAGE = "This link is invalid, expired, or has already been used."
RECENT_REAUTHENTICATION = timedelta(minutes=10)
REGISTRATION_MESSAGE = "Check your email for the next account-creation step."


def sender_for(request: Request) -> EmailSender:
    return cast(EmailSender, request.app.state.email_sender)


def public_origin(request: Request) -> str:
    return runtime_settings(request).public_origin or str(request.base_url).rstrip("/")


def deliver(
    session: Session,
    request: Request,
    *,
    purpose: str,
    message: EmailMessage,
    action_token_id: int | None,
    user_id: int | None,
    actor_label: str,
) -> None:
    attempt = deliver_message(
        session,
        sender_for(request),
        purpose=purpose,
        message=message,
        action_token_id=action_token_id,
    )
    record_security_event(
        session,
        "email_delivery_succeeded" if attempt.status == "sent" else "email_delivery_failed",
        user_id=user_id,
        actor_label=actor_label,
        details={"purpose": purpose, "failure_code": attempt.failure_code},
    )
    session.commit()


@router.get("/registration", response_model=RegistrationConfigurationRead)
def registration_configuration(request: Request) -> RegistrationConfigurationRead:
    return RegistrationConfigurationRead(mode=runtime_settings(request).registration_mode)


@router.post("/registration", response_model=MessageRead)
def register_account(
    details: RegistrationRequest,
    request: Request,
    session: DatabaseSession,
) -> MessageRead:
    validate_request_origin(request)
    if runtime_settings(request).registration_mode != "open" and details.invitation_token is None:
        raise ApiError(
            status_code=403,
            code="registration_unavailable",
            message="Account creation is not currently available.",
        )

    account = account_for_email(session, str(details.email), for_update=True)
    if account is not None and account.security_state == ACTIVE:
        raise ApiError(
            status_code=409,
            code="account_already_registered",
            message="An account with this email address is already registered.",
        )
    matches = password_matches(account, details.password)
    created = account is None
    if account is None:
        account = create_account(
            session,
            display_name=details.display_name,
            email=str(details.email),
            password=details.password,
            actor_label="Self Registration",
        )

    if details.invitation_token is not None and account.security_state == PENDING_VERIFICATION:
        try:
            claim_invitation_for_registration(
                session,
                raw_token=details.invitation_token,
                account=account,
            )
        except ValueError as error:
            raise ApiError(
                status_code=400,
                code="invalid_invitation",
                message=str(error),
            ) from error

    if account.security_state == PENDING_VERIFICATION and (created or matches):
        issued = issue_action(
            session,
            purpose=EMAIL_VERIFICATION,
            canonical_email=account.canonical_email,
            display_email=account.display_email,
            lifetime=VERIFICATION_LIFETIME,
            user_id=account.id,
        )
        session.commit()
        link = action_link(public_origin(request), "verify-email", issued.raw_token)
        deliver(
            session,
            request,
            purpose=EMAIL_VERIFICATION,
            message=verification_message(account.display_email, link),
            action_token_id=issued.record.id,
            user_id=account.id,
            actor_label=account.display_name,
        )
    return MessageRead(message=REGISTRATION_MESSAGE)


@router.post("/verification/confirm", response_model=MessageRead)
def confirm_verification(
    details: TokenRequest,
    request: Request,
    session: DatabaseSession,
) -> MessageRead:
    validate_request_origin(request)
    action = valid_action(
        session,
        purpose=EMAIL_VERIFICATION,
        raw_token=details.token,
    )
    account = session.get(User, action.user_id) if action is not None else None
    if action is None or account is None or account.security_state != PENDING_VERIFICATION:
        raise ApiError(
            status_code=400, code="invalid_account_action", message=INVALID_TOKEN_MESSAGE
        )
    moment = utc_now()
    account.email_verified_at = moment
    account.security_state = ACTIVE
    consume_action(action, now=moment)
    accept_claimed_invitations(session, account)
    record_security_event(
        session,
        "email_verified",
        user_id=account.id,
        actor_label=account.display_name,
    )
    session.commit()
    return MessageRead(message="Email verified. You can now sign in.")


@router.post("/password-reset/request", response_model=MessageRead)
def request_password_reset(
    details: EmailActionRequest,
    request: Request,
    session: DatabaseSession,
) -> MessageRead:
    validate_request_origin(request)
    account = account_for_email(session, str(details.email), for_update=True)
    if (
        account is not None
        and account.security_state == ACTIVE
        and account.email_verified_at is not None
    ):
        issued = issue_action(
            session,
            purpose=PASSWORD_RESET,
            canonical_email=account.canonical_email,
            display_email=account.display_email,
            lifetime=PASSWORD_RESET_LIFETIME,
            user_id=account.id,
        )
        record_security_event(
            session,
            "password_reset_requested",
            user_id=account.id,
            actor_label=account.display_name,
        )
        session.commit()
        link = action_link(public_origin(request), "reset-password", issued.raw_token)
        deliver(
            session,
            request,
            purpose=PASSWORD_RESET,
            message=password_reset_message(account.display_email, link),
            action_token_id=issued.record.id,
            user_id=account.id,
            actor_label=account.display_name,
        )
    return MessageRead(message=GENERIC_REQUEST_MESSAGE)


@router.post("/password-reset/confirm", response_model=MessageRead)
def confirm_password_reset(
    details: PasswordResetRequest,
    request: Request,
    session: DatabaseSession,
) -> MessageRead:
    validate_request_origin(request)
    action = valid_action(session, purpose=PASSWORD_RESET, raw_token=details.token)
    account = session.get(User, action.user_id) if action is not None else None
    if action is None or account is None or account.security_state != ACTIVE:
        raise ApiError(
            status_code=400, code="invalid_account_action", message=INVALID_TOKEN_MESSAGE
        )
    consume_action(action)
    reset_account_password(session, account, details.password, actor_label="Account Recovery")
    revoke_user_actions(session, account.id)
    session.commit()
    return MessageRead(message="Password changed. Sign in with your new password.")


@router.post("/password-change", response_model=MessageRead)
def change_password(
    details: PasswordChangeRequest,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> MessageRead:
    if details.password != details.password_confirmation:
        raise ApiError(
            status_code=400,
            code="password_confirmation_mismatch",
            message="The new passwords do not match.",
        )
    if not reauthenticate_session(session, authenticated, details.current_password):
        record_security_event(
            session,
            "reauthentication_failed",
            user_id=authenticated.id,
            actor_label=authenticated.display_name,
            details={"source": "password_change"},
        )
        session.commit()
        raise ApiError(
            status_code=400,
            code="reauthentication_failed",
            message="Your current password could not be confirmed.",
        )

    account = session.get(User, authenticated.id)
    if account is None:
        raise ApiError(
            status_code=401, code="authentication_required", message="Sign in to continue"
        )
    if password_matches(account, details.password):
        raise ApiError(
            status_code=409,
            code="password_unchanged",
            message="Choose a password different from your current password.",
        )

    change_account_password(
        session,
        account,
        details.password,
        current_session_id=authenticated.session_id,
        actor_label=authenticated.display_name,
    )
    revoke_user_actions(session, account.id)
    session.commit()
    return MessageRead(message="Password changed successfully.")


@router.post("/email-change/request", response_model=MessageRead)
def request_email_change(
    details: EmailChangeRequest,
    request: Request,
    session: DatabaseSession,
    authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> MessageRead:
    if not reauthenticate_session(session, authenticated, details.password):
        record_security_event(
            session,
            "reauthentication_failed",
            user_id=authenticated.id,
            actor_label=authenticated.display_name,
            details={"source": "email_change"},
        )
        session.commit()
        raise ApiError(
            status_code=401,
            code="reauthentication_failed",
            message="Your password could not be confirmed.",
        )
    if not session_was_recently_reauthenticated(
        session,
        authenticated.session_id,
        maximum_age=RECENT_REAUTHENTICATION,
    ):
        raise ApiError(
            status_code=401,
            code="recent_authentication_required",
            message="Confirm your password again to continue.",
        )

    account = session.get(User, authenticated.id)
    if account is None:
        raise ApiError(
            status_code=401, code="authentication_required", message="Sign in to continue"
        )
    identity = normalise_email(str(details.email))
    existing = account_for_email(session, identity.canonical)
    if existing is not None and existing.id != account.id:
        raise ApiError(
            status_code=409,
            code="email_change_unavailable",
            message="That email address cannot be used.",
        )
    if identity.canonical == account.canonical_email:
        raise ApiError(
            status_code=409,
            code="email_unchanged",
            message="Enter a different email address.",
        )

    issued = issue_action(
        session,
        purpose=EMAIL_CHANGE,
        canonical_email=identity.canonical,
        display_email=identity.display,
        lifetime=EMAIL_CHANGE_LIFETIME,
        user_id=account.id,
    )
    record_security_event(
        session,
        "email_change_requested",
        user_id=account.id,
        actor_label=account.display_name,
    )
    session.commit()
    link = action_link(public_origin(request), "confirm-email", issued.raw_token)
    deliver(
        session,
        request,
        purpose=EMAIL_CHANGE,
        message=email_change_message(identity.display, link),
        action_token_id=issued.record.id,
        user_id=account.id,
        actor_label=account.display_name,
    )
    return MessageRead(message="Check the new address for a confirmation link.")


@router.post("/email-change/confirm", response_model=MessageRead)
def confirm_email_change(
    details: TokenRequest,
    request: Request,
    session: DatabaseSession,
) -> MessageRead:
    validate_request_origin(request)
    action = valid_action(session, purpose=EMAIL_CHANGE, raw_token=details.token)
    account = session.get(User, action.user_id) if action is not None else None
    if action is None or account is None or account.security_state != ACTIVE:
        raise ApiError(
            status_code=400, code="invalid_account_action", message=INVALID_TOKEN_MESSAGE
        )
    existing = account_for_email(session, action.canonical_email)
    if existing is not None and existing.id != account.id:
        raise ApiError(
            status_code=400, code="invalid_account_action", message=INVALID_TOKEN_MESSAGE
        )

    old_email = account.display_email
    moment = utc_now()
    account.canonical_email = action.canonical_email
    account.display_email = action.display_email
    account.email_verified_at = moment
    consume_action(action, now=moment)
    revoke_user_actions(session, account.id, now=moment)
    revoke_all_sessions(session, account.id, now=moment)
    record_security_event(
        session,
        "account_email_changed",
        user_id=account.id,
        actor_label=account.display_name,
    )
    session.commit()
    deliver(
        session,
        request,
        purpose="email_change_notice",
        message=email_changed_notice(old_email),
        action_token_id=None,
        user_id=account.id,
        actor_label=account.display_name,
    )
    return MessageRead(message="Email changed. Sign in again with your new address.")


@router.get("/development/email-outbox", response_model=list[DevelopmentEmailRead])
def development_email_outbox(request: Request, response: Response) -> list[DevelopmentEmailRead]:
    if runtime_settings(request).environment == "production":
        raise ApiError(status_code=404, code="not_found", message="Not found")
    sender = sender_for(request)
    if not isinstance(sender, DevelopmentOutbox):
        raise ApiError(status_code=404, code="not_found", message="Not found")
    response.headers["Cache-Control"] = "no-store"
    return [
        DevelopmentEmailRead(
            id=message.id,
            recipient=message.recipient,
            subject=message.subject,
            text=message.text,
        )
        for message in sender.messages
    ]

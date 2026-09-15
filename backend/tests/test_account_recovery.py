"""Transactional email and single-use account recovery proofs."""

from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select

from authentication.account_actions import (
    EMAIL_VERIFICATION,
    INVITATION,
    INVITATION_LIFETIME,
    VERIFICATION_LIFETIME,
    issue_action,
    valid_action,
)
from authentication.email_delivery import (
    EmailDeliveryError,
    EmailMessage,
    ResendEmailSender,
    create_email_sender,
)
from authentication.models import AccountActionToken, EmailDeliveryAttempt
from authentication.service import account_for_email, create_account
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings

PASSWORD = "current-password"
NEW_PASSWORD = "replacement-password"
EMAIL = "Operator@Example.org"
ORIGIN = "http://testserver"


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("leave_planner_csrf")
    assert token
    return {"Origin": ORIGIN, "X-CSRF-Token": token}


def action_token(text: str) -> str:
    for word in text.split():
        if "?action=" in word:
            return parse_qs(urlparse(word).query)["token"][0]
    raise AssertionError("The message did not contain an account-action link")


def prepared_app(tmp_path: Path, *, verified: bool = True) -> tuple[FastAPI, Settings]:
    settings = Settings(environment="test", data_dir=tmp_path, public_origin=ORIGIN)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            create_account(
                session,
                display_name="Primary Operator",
                email=EMAIL,
                password=PASSWORD,
                verified_at=datetime.now(UTC) if verified else None,
            )
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=tmp_path / "missing"), settings


def outbox(client: TestClient) -> list[dict[str, str]]:
    response = client.get("/api/auth/development/email-outbox")
    assert response.status_code == 200
    return cast(list[dict[str, str]], response.json())


def test_password_reset_is_generic_hashed_single_use_and_revokes_sessions(tmp_path: Path) -> None:
    app, settings = prepared_app(tmp_path)
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200

        known = client.post(
            "/api/auth/password-reset/request",
            json={"email": EMAIL},
            headers={"Origin": ORIGIN},
        )
        unknown = client.post(
            "/api/auth/password-reset/request",
            json={"email": "unknown@example.org"},
            headers={"Origin": ORIGIN},
        )
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()
        messages = outbox(client)
        assert len(messages) == 1
        raw_token = action_token(messages[0]["text"])

        engine = create_database_engine(settings.resolved_database_url)
        try:
            with session_scope(create_session_factory(engine)) as session:
                stored = session.scalar(select(AccountActionToken))
                assert stored is not None
                assert stored.token_hash != raw_token
                persisted_action = " ".join(
                    str(value) for key, value in stored.__dict__.items() if not key.startswith("_")
                )
                assert raw_token not in persisted_action
                attempt = session.scalar(select(EmailDeliveryAttempt))
                assert attempt is not None
                assert attempt.recipient_hint == "O***@Example.org"
                persisted_attempt = " ".join(
                    str(value) for key, value in attempt.__dict__.items() if not key.startswith("_")
                )
                assert EMAIL not in persisted_attempt
        finally:
            engine.dispose()

        changed = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": raw_token, "password": NEW_PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert changed.status_code == 200
        assert client.get("/api/auth/session").json()["authenticated"] is False
        reused = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": raw_token, "password": NEW_PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert reused.status_code == 400
        assert reused.json()["error"]["code"] == "invalid_account_action"
        assert (
            client.post(
                "/api/auth/login",
                json={"email": EMAIL, "password": NEW_PASSWORD},
                headers={"Origin": ORIGIN},
            ).status_code
            == 200
        )


def test_resending_verification_revokes_the_previous_link(tmp_path: Path) -> None:
    app, settings = prepared_app(tmp_path, verified=False)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = account_for_email(session, EMAIL)
            assert account is not None
            first_action = issue_action(
                session,
                purpose=EMAIL_VERIFICATION,
                canonical_email=account.canonical_email,
                display_email=account.display_email,
                lifetime=VERIFICATION_LIFETIME,
                user_id=account.id,
            )
            second_action = issue_action(
                session,
                purpose=EMAIL_VERIFICATION,
                canonical_email=account.canonical_email,
                display_email=account.display_email,
                lifetime=VERIFICATION_LIFETIME,
                user_id=account.id,
            )
            first_token = first_action.raw_token
            second_token = second_action.raw_token
    finally:
        engine.dispose()

    with TestClient(app) as client:
        first = client.post(
            "/api/auth/verification/confirm",
            json={"token": first_token},
            headers={"Origin": ORIGIN},
        )
        assert first.status_code == 400
        second = client.post(
            "/api/auth/verification/confirm",
            json={"token": second_token},
            headers={"Origin": ORIGIN},
        )
        assert second.status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            ).status_code
            == 200
        )


def test_expired_action_and_invitation_lifetime_are_enforced(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            moment = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
            issued = issue_action(
                session,
                purpose=INVITATION,
                canonical_email="member@example.org",
                display_email="member@example.org",
                lifetime=INVITATION_LIFETIME,
                user_id=None,
                workspace_id=1,
                now=moment,
            )
            assert issued.record.expires_at == moment + timedelta(days=7)
            assert (
                valid_action(
                    session,
                    purpose=INVITATION,
                    raw_token=issued.raw_token,
                    now=moment + timedelta(days=7),
                )
                is None
            )
    finally:
        engine.dispose()


def test_email_change_requires_password_confirms_new_address_and_notifies_old(
    tmp_path: Path,
) -> None:
    app, _settings = prepared_app(tmp_path)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            ).status_code
            == 200
        )
        rejected = client.post(
            "/api/auth/email-change/request",
            json={"email": "new@example.org", "password": "wrong-password"},
            headers=csrf_headers(client),
        )
        assert rejected.status_code == 401

        requested = client.post(
            "/api/auth/email-change/request",
            json={"email": "New@Example.org", "password": PASSWORD},
            headers=csrf_headers(client),
        )
        assert requested.status_code == 200
        raw_token = action_token(outbox(client)[0]["text"])
        confirmed = client.post(
            "/api/auth/email-change/confirm",
            json={"token": raw_token},
            headers={"Origin": ORIGIN},
        )
        assert confirmed.status_code == 200
        messages = outbox(client)
        assert [message["recipient"] for message in messages] == ["New@example.org", EMAIL]
        assert client.get("/api/auth/session").json()["authenticated"] is False
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "new@example.org", "password": PASSWORD},
                headers={"Origin": ORIGIN},
            ).status_code
            == 200
        )


class FailingSender:
    def send(self, _message: EmailMessage, *, idempotency_key: str) -> str:
        assert idempotency_key
        raise EmailDeliveryError("provider_unavailable")


def test_delivery_failure_is_redacted_and_a_resend_issues_one_replacement(tmp_path: Path) -> None:
    app, settings = prepared_app(tmp_path)
    with TestClient(app) as client:
        app.state.email_sender = FailingSender()
        response = client.post(
            "/api/auth/password-reset/request",
            json={"email": EMAIL},
            headers={"Origin": ORIGIN},
        )
        assert response.status_code == 200

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            failed = session.scalar(select(EmailDeliveryAttempt))
            assert failed is not None
            assert failed.status == "failed"
            assert failed.failure_code == "provider_unavailable"
            persisted_attempt = " ".join(
                str(value) for key, value in failed.__dict__.items() if not key.startswith("_")
            )
            assert EMAIL not in persisted_attempt
            first_action = session.scalar(select(AccountActionToken))
            assert first_action is not None
            first_hash = first_action.token_hash
    finally:
        engine.dispose()

    app = create_app(settings=settings, frontend_dist=tmp_path / "missing")
    with TestClient(app) as client:
        client.post(
            "/api/auth/password-reset/request",
            json={"email": EMAIL},
            headers={"Origin": ORIGIN},
        )
        assert len(outbox(client)) == 1

    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            actions = tuple(
                session.scalars(select(AccountActionToken).order_by(AccountActionToken.id))
            )
            assert len(actions) == 2
            assert actions[0].token_hash == first_hash
            assert actions[0].revoked_at is not None
            assert actions[1].revoked_at is None
    finally:
        engine.dispose()


class FakeResponse(AbstractContextManager["FakeResponse"]):
    def read(self) -> bytes:
        return b'{"id":"provider-message-id"}'

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def test_resend_adapter_uses_https_authorization_and_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        observed["request"] = request
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("authentication.email_delivery.urlopen", fake_urlopen)
    sender = ResendEmailSender(
        api_key="re_secret",
        sender="Leave Planner <notifications@merydio.co.uk>",
    )
    message_id = sender.send(
        EmailMessage("recipient@example.org", "Subject", "Body"),
        idempotency_key="password_reset/example",
    )
    request = observed["request"]
    assert message_id == "provider-message-id"
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer re_secret"
    assert request.get_header("Idempotency-key") == "password_reset/example"
    assert observed["timeout"] == 10


def test_production_requires_resend_configuration(tmp_path: Path) -> None:
    database = SecretStr("postgresql+psycopg://leave_planner:secret@database/leave_planner")
    with pytest.raises(RuntimeError, match="Resend email provider"):
        create_email_sender(
            Settings(
                environment="production",
                database_url=database,
                public_origin="https://app.merydio.co.uk",
            )
        )
    with pytest.raises(ValidationError, match="resend_api_key_file"):
        Settings(
            environment="production",
            database_url=database,
            public_origin="https://app.merydio.co.uk",
            email_provider="resend",
        )

    key_path = tmp_path / "resend-key"
    key_path.write_text("re_secret\n", encoding="utf-8")
    settings = Settings(
        environment="production",
        database_url=database,
        public_origin="https://app.merydio.co.uk",
        email_provider="resend",
        resend_api_key_file=key_path,
    )
    assert settings.resend_api_key == "re_secret"

"""Workspace-management acceptance and authorization tests."""

import gc
import re
import warnings
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from authentication.models import User, UserSession
from authentication.service import create_account
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.management import purge_closed_workspace
from workspaces.models import ADMIN_ROLE, MEMBER_ROLE, OWNER_ROLE, Workspace, WorkspaceMembership

OWNER_EMAIL = "owner@example.org"
ADMIN_EMAIL = "admin@example.org"
MEMBER_EMAIL = "member@example.org"
PASSWORD = "workspace-password"


@pytest.fixture(autouse=True)
def collect_disposed_sqlite_wrappers() -> Iterator[None]:
    """Finalize disposed SQLAlchemy wrappers before Python 3.14 reports them later."""

    yield
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()


def workspace_app(
    tmp_path: Path,
    *,
    with_consultant: bool = True,
) -> tuple[FastAPI, Engine, sessionmaker[Session], dict[str, int], int | None]:
    settings = Settings(environment="test", data_dir=tmp_path, registration_mode="open")
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        owner = create_account(
            session,
            display_name="Primary Owner",
            email=OWNER_EMAIL,
            password=PASSWORD,
            verified_at=datetime.now(UTC),
        )
        admin = create_account(
            session,
            display_name="Workspace Admin",
            email=ADMIN_EMAIL,
            password=PASSWORD,
            verified_at=datetime.now(UTC),
        )
        member = create_account(
            session,
            display_name="Workspace Member",
            email=MEMBER_EMAIL,
            password=PASSWORD,
            verified_at=datetime.now(UTC),
        )
        workspace = session.get(Workspace, 1)
        assert workspace is not None
        workspace.name = "Consultant Team"
        session.add(
            WorkspaceMembership(workspace_id=workspace.id, user_id=owner.id, role=OWNER_ROLE)
        )
        consultant_id = None
        if with_consultant:
            consultant = Consultant(workspace_id=workspace.id, name="Dr Member")
            session.add(consultant)
            session.flush()
            consultant_id = consultant.id
        account_ids = {"owner": owner.id, "admin": admin.id, "member": member.id}
    app = create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")
    return app, engine, factory, account_ids, consultant_id


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    csrf = client.cookies.get("leave_planner_csrf")
    assert csrf
    return {"Origin": "http://testserver", "X-CSRF-Token": csrf}


def latest_invitation_token(client: TestClient) -> str:
    messages = client.get("/api/auth/development/email-outbox").json()
    assert messages
    match = re.search(r"token=([^\s]+)", messages[-1]["text"])
    assert match
    return match.group(1)


def test_owner_invites_existing_admin_and_target_must_accept_with_matching_email(
    tmp_path: Path,
) -> None:
    app, engine, _factory, _account_ids, _consultant_id = workspace_app(tmp_path)
    try:
        with TestClient(app) as owner_client:
            headers = sign_in(owner_client, OWNER_EMAIL)
            response = owner_client.post(
                "/api/workspaces/1/invitations",
                json={"email": ADMIN_EMAIL, "role": "admin"},
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["invitations"][0]["role"] == ADMIN_ROLE
            token = latest_invitation_token(owner_client)

        with TestClient(app) as wrong_client:
            wrong_headers = sign_in(wrong_client, MEMBER_EMAIL)
            denied = wrong_client.post(
                "/api/workspaces/invitations/accept",
                json={"token": token},
                headers=wrong_headers,
            )
            assert denied.status_code == 403

        with TestClient(app) as admin_client:
            admin_headers = sign_in(admin_client, ADMIN_EMAIL)
            accepted = admin_client.post(
                "/api/workspaces/invitations/accept",
                json={"token": token},
                headers=admin_headers,
            )
            assert accepted.status_code == 200
            assert accepted.json()["active_workspace_id"] == 1
            assert accepted.json()["memberships"][0]["role"] == ADMIN_ROLE

            reused = admin_client.post(
                "/api/workspaces/invitations/accept",
                json={"token": token},
                headers=admin_headers,
            )
            assert reused.status_code == 409
    finally:
        engine.dispose()


def test_invited_new_account_joins_only_after_email_verification(tmp_path: Path) -> None:
    app, engine, factory, _account_ids, consultant_id = workspace_app(tmp_path)
    assert consultant_id is not None
    invited_email = "new-member@example.org"
    try:
        with TestClient(app) as owner_client:
            headers = sign_in(owner_client, OWNER_EMAIL)
            invited = owner_client.post(
                "/api/workspaces/1/invitations",
                json={
                    "email": invited_email,
                    "role": "member",
                    "linked_consultant_id": consultant_id,
                },
                headers=headers,
            )
            assert invited.status_code == 200
            invitation_token = latest_invitation_token(owner_client)

            registered = owner_client.post(
                "/api/auth/registration",
                json={
                    "display_name": "New Member",
                    "email": invited_email,
                    "password": PASSWORD,
                    "invitation_token": invitation_token,
                },
                headers={"Origin": "http://testserver"},
            )
            assert registered.status_code == 200
            verification_token = latest_invitation_token(owner_client)

            with session_scope(factory) as session:
                new_account_id = session.scalar(
                    select(User.id).where(User.canonical_email == invited_email)
                )
                assert new_account_id is not None
                assert (
                    session.scalar(
                        select(WorkspaceMembership).where(
                            WorkspaceMembership.workspace_id == 1,
                            WorkspaceMembership.user_id == new_account_id,
                        )
                    )
                    is None
                )

            verified = owner_client.post(
                "/api/auth/verification/confirm",
                json={"token": verification_token},
                headers={"Origin": "http://testserver"},
            )
            assert verified.status_code == 200

        with TestClient(app) as member_client:
            sign_in(member_client, invited_email)
            context = member_client.get("/api/auth/session").json()["workspace"]
            assert context["state"] == "active"
            assert context["memberships"][0]["role"] == MEMBER_ROLE
            assert context["memberships"][0]["linked_consultant_id"] == consultant_id
    finally:
        engine.dispose()


def test_admin_can_manage_members_but_cannot_invite_or_change_admins(tmp_path: Path) -> None:
    app, engine, factory, account_ids, consultant_id = workspace_app(tmp_path)
    assert consultant_id is not None
    try:
        with session_scope(factory) as session:
            session.add(
                WorkspaceMembership(
                    workspace_id=1,
                    user_id=account_ids["admin"],
                    role=ADMIN_ROLE,
                )
            )
            session.add(
                WorkspaceMembership(
                    workspace_id=1,
                    user_id=account_ids["member"],
                    role=MEMBER_ROLE,
                    linked_consultant_id=consultant_id,
                )
            )

        with TestClient(app) as client:
            headers = sign_in(client, ADMIN_EMAIL)
            denied_invite = client.post(
                "/api/workspaces/1/invitations",
                json={"email": "another@example.org", "role": "admin"},
                headers=headers,
            )
            assert denied_invite.status_code == 403

            detail = client.get("/api/workspaces/1/management").json()
            admin_membership = next(
                person["membership_id"] for person in detail["people"] if person["role"] == "admin"
            )
            member_membership = next(
                person["membership_id"] for person in detail["people"] if person["role"] == "member"
            )
            denied_change = client.patch(
                f"/api/workspaces/1/members/{admin_membership}",
                json={"role": "member", "linked_consultant_id": consultant_id},
                headers=headers,
            )
            assert denied_change.status_code == 403
            allowed_change = client.patch(
                f"/api/workspaces/1/members/{member_membership}",
                json={"role": "member", "linked_consultant_id": consultant_id},
                headers=headers,
            )
            assert allowed_change.status_code == 200
    finally:
        engine.dispose()


def test_member_removal_clears_active_workspace_sessions(tmp_path: Path) -> None:
    app, engine, factory, account_ids, consultant_id = workspace_app(tmp_path)
    assert consultant_id is not None
    try:
        with session_scope(factory) as session:
            session.add(
                WorkspaceMembership(
                    workspace_id=1,
                    user_id=account_ids["member"],
                    role=MEMBER_ROLE,
                    linked_consultant_id=consultant_id,
                )
            )
        with TestClient(app) as member_client:
            sign_in(member_client, MEMBER_EMAIL)
            with TestClient(app) as owner_client:
                headers = sign_in(owner_client, OWNER_EMAIL)
                detail = owner_client.get("/api/workspaces/1/management").json()
                membership_id = next(
                    person["membership_id"]
                    for person in detail["people"]
                    if person["role"] == "member"
                )
                removed = owner_client.delete(
                    f"/api/workspaces/1/members/{membership_id}", headers=headers
                )
                assert removed.status_code == 200

            context = member_client.get("/api/auth/session").json()["workspace"]
            assert context["state"] == "onboarding"
            assert context["active_workspace_id"] is None

        with session_scope(factory) as session:
            member_sessions = tuple(
                session.scalars(
                    select(UserSession).where(UserSession.user_id == account_ids["member"])
                )
            )
            assert all(stored.active_workspace_id is None for stored in member_sessions)
    finally:
        engine.dispose()


def test_owner_transfer_and_workspace_close_recovery_are_explicit(tmp_path: Path) -> None:
    app, engine, factory, account_ids, _consultant_id = workspace_app(tmp_path)
    try:
        with session_scope(factory) as session:
            session.add(
                WorkspaceMembership(
                    workspace_id=1,
                    user_id=account_ids["admin"],
                    role=ADMIN_ROLE,
                )
            )
        with TestClient(app) as owner_client:
            owner_headers = sign_in(owner_client, OWNER_EMAIL)
            detail = owner_client.get("/api/workspaces/1/management").json()
            admin_membership = next(
                person["membership_id"] for person in detail["people"] if person["role"] == "admin"
            )
            requested = owner_client.post(
                "/api/workspaces/1/ownership-transfers",
                json={"target_membership_id": admin_membership},
                headers=owner_headers,
            )
            assert requested.status_code == 200
            transfer_id = requested.json()["transfer"]["transfer_id"]

        with TestClient(app) as admin_client:
            admin_headers = sign_in(admin_client, ADMIN_EMAIL)
            accepted = admin_client.post(
                f"/api/workspaces/1/ownership-transfers/{transfer_id}/accept",
                headers=admin_headers,
            )
            assert accepted.status_code == 200
            assert accepted.json()["current_role"] == OWNER_ROLE

            closed = admin_client.post(
                "/api/workspaces/1/close",
                json={"confirmation_name": "Consultant Team", "password": PASSWORD},
                headers=admin_headers,
            )
            assert closed.status_code == 200
            assert closed.json()["state"] == "onboarding"
            assert admin_client.get("/api/workspaces/1/management").json()["status"] == "closed"

            recovered = admin_client.post(
                "/api/workspaces/1/recover",
                json={"confirmation_name": "recover", "password": PASSWORD},
                headers=admin_headers,
            )
            assert recovered.status_code == 200
            assert admin_client.get("/api/workspaces/1/management").json()["status"] == "active"
    finally:
        engine.dispose()


def test_empty_setup_workspace_deletes_but_history_requires_closure(tmp_path: Path) -> None:
    app, engine, _factory, _account_ids, _consultant_id = workspace_app(
        tmp_path, with_consultant=False
    )
    try:
        with TestClient(app) as client:
            headers = sign_in(client, OWNER_EMAIL)
            impact = client.get("/api/workspaces/1/impact").json()
            assert impact["can_delete_immediately"] is True
            deleted = client.request(
                "DELETE",
                "/api/workspaces/1",
                json={"confirmation_name": "Consultant Team"},
                headers=headers,
            )
            assert deleted.status_code == 200
            assert deleted.json()["state"] == "onboarding"
    finally:
        engine.dispose()


def test_server_purge_waits_for_closed_workspace_recovery_deadline(tmp_path: Path) -> None:
    app, engine, factory, _account_ids, _consultant_id = workspace_app(tmp_path)
    try:
        with TestClient(app) as client:
            headers = sign_in(client, OWNER_EMAIL)
            closed = client.post(
                "/api/workspaces/1/close",
                json={"confirmation_name": "Consultant Team", "password": PASSWORD},
                headers=headers,
            )
            assert closed.status_code == 200

        with session_scope(factory) as session:
            workspace = session.get(Workspace, 1)
            assert workspace is not None
            assert workspace.purge_after is not None
            with pytest.raises(ValueError, match="recovery period has not ended"):
                purge_closed_workspace(
                    session,
                    workspace_id=1,
                    confirmation_name="Consultant Team",
                    now=workspace.purge_after - timedelta(seconds=1),
                )

        with session_scope(factory) as session:
            workspace = session.get(Workspace, 1)
            assert workspace is not None
            assert workspace.purge_after is not None
            purge_closed_workspace(
                session,
                workspace_id=1,
                confirmation_name="Consultant Team",
                now=workspace.purge_after + timedelta(seconds=1),
            )

        with session_scope(factory) as session:
            assert session.get(Workspace, 1) is None
            assert session.scalar(select(Consultant.id)) is None
    finally:
        engine.dispose()

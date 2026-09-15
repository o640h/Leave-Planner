"""Workspace role, active-selection, and portable isolation proofs."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from authentication.models import User
from authentication.service import create_account
from consultants.models import Consultant
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import (
    ADMIN_ROLE,
    MEMBER_ROLE,
    OWNER_ROLE,
    Workspace,
    WorkspaceMembership,
)
from workspaces.service import current_access

PASSWORD = "individual-account-password"


def create_workspace_app(
    tmp_path: Path,
    *,
    roles: tuple[str, ...],
) -> tuple[FastAPI, Settings, list[int]]:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    workspace_ids: list[int] = []
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = create_account(
                session,
                display_name="Workspace Operator",
                email="operator@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            existing = session.get(Workspace, 1)
            assert existing is not None
            existing.name = "Clinical Services"
            workspaces = [existing]
            for number in range(2, len(roles) + 1):
                workspace = Workspace(name=f"Workspace {number}")
                session.add(workspace)
                session.flush()
                workspaces.append(workspace)
            for workspace, role in zip(workspaces, roles, strict=True):
                session.add(
                    WorkspaceMembership(
                        workspace_id=workspace.id,
                        user_id=account.id,
                        role=role,
                    )
                )
                workspace_ids.append(workspace.id)
    finally:
        engine.dispose()
    app = create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")
    return app, settings, workspace_ids


def sign_in(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "operator@example.org", "password": PASSWORD},
    )
    assert response.status_code == 200
    csrf = client.cookies.get("leave_planner_csrf")
    assert csrf
    return {"X-CSRF-Token": csrf, "Origin": "http://testserver"}


def test_multiple_memberships_require_selection_and_remember_the_last_workspace(
    tmp_path: Path,
) -> None:
    app, _settings, workspace_ids = create_workspace_app(tmp_path, roles=(OWNER_ROLE, ADMIN_ROLE))
    with TestClient(app) as client:
        headers = sign_in(client)
        context = client.get("/api/auth/session").json()["workspace"]
        assert context["state"] == "selection_required"
        assert context["active_workspace_id"] is None
        assert [item["workspace_id"] for item in context["memberships"]] == workspace_ids
        assert client.get("/api/consultants").json()["error"]["code"] == (
            "workspace_selection_required"
        )

        selected = client.post(
            "/api/workspaces/active",
            json={"workspace_id": workspace_ids[1]},
            headers=headers,
        )
        assert selected.status_code == 200
        assert selected.json()["active_workspace_id"] == workspace_ids[1]
        assert client.get("/api/consultants").status_code == 200

        client.post("/api/auth/logout", headers=headers)
        sign_in(client)
        restored = client.get("/api/auth/session").json()["workspace"]
        assert restored["state"] == "active"
        assert restored["active_workspace_id"] == workspace_ids[1]


def test_guessed_workspace_cannot_be_selected(tmp_path: Path) -> None:
    app, _settings, _workspace_ids = create_workspace_app(tmp_path, roles=(OWNER_ROLE,))
    with TestClient(app) as client:
        headers = sign_in(client)
        response = client.post(
            "/api/workspaces/active",
            json={"workspace_id": 999_999},
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "workspace_not_found"


def test_member_role_cannot_enter_the_operator_planner(tmp_path: Path) -> None:
    app, _settings, _workspace_ids = create_workspace_app(tmp_path, roles=(MEMBER_ROLE,))
    with TestClient(app) as client:
        sign_in(client)
        response = client.get("/api/consultants")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "workspace_role_denied"


def test_membership_constraints_prevent_two_owners_and_cross_workspace_links(
    tmp_path: Path,
) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            first = create_account(
                session,
                display_name="First Owner",
                email="first@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            create_account(
                session,
                display_name="Second Owner",
                email="second@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            session.add(WorkspaceMembership(workspace_id=1, user_id=first.id, role=OWNER_ROLE))

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            second_account = session.scalar(
                select(User).where(User.canonical_email == "second@example.org")
            )
            assert second_account is not None
            session.add(
                WorkspaceMembership(workspace_id=1, user_id=second_account.id, role=OWNER_ROLE)
            )

        with session_scope(factory) as session:
            linked_account = session.scalar(
                select(User).where(User.canonical_email == "second@example.org")
            )
            assert linked_account is not None
            foreign_workspace = Workspace(name="Foreign")
            session.add(foreign_workspace)
            session.flush()
            foreign_consultant = Consultant(
                workspace_id=foreign_workspace.id,
                name="Foreign Consultant",
            )
            session.add(foreign_consultant)
            session.flush()

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            linked_account = session.scalar(
                select(User).where(User.canonical_email == "second@example.org")
            )
            selected_consultant = session.scalar(
                select(Consultant).where(Consultant.name == "Foreign Consultant")
            )
            assert linked_account is not None
            assert selected_consultant is not None
            session.add(
                WorkspaceMembership(
                    workspace_id=1,
                    user_id=linked_account.id,
                    role=MEMBER_ROLE,
                    linked_consultant_id=selected_consultant.id,
                )
            )
    finally:
        engine.dispose()


def test_private_service_access_requires_an_explicit_bound_workspace(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with (
            session_scope(create_session_factory(engine)) as session,
            pytest.raises(RuntimeError, match="workspace must be bound"),
        ):
            current_access(session)
    finally:
        engine.dispose()

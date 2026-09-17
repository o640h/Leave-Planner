"""Authenticated policy catalogue and safe PDF delivery tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from authentication.service import create_account
from database import create_database_engine, create_session_factory, session_scope
from main import create_app
from migrations import upgrade_database
from settings import Settings
from workspaces.models import ADMIN_ROLE, MEMBER_ROLE, OWNER_ROLE, Workspace, WorkspaceMembership

PASSWORD = "policy-library-password"


def policy_app(tmp_path: Path, role: str) -> FastAPI:
    settings = Settings(environment="test", data_dir=tmp_path)
    upgrade_database(settings.resolved_database_url)
    engine = create_database_engine(settings.resolved_database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            account = create_account(
                session,
                display_name="Policy Reader",
                email="reader@example.org",
                password=PASSWORD,
                verified_at=datetime.now(UTC),
            )
            workspace = session.scalar(select(Workspace))
            assert workspace is not None
            session.add(
                WorkspaceMembership(workspace_id=workspace.id, user_id=account.id, role=role)
            )
            account.last_workspace_id = workspace.id
    finally:
        engine.dispose()
    return create_app(settings=settings, frontend_dist=tmp_path / "missing-frontend")


def sign_in(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "reader@example.org", "password": PASSWORD},
    )
    assert response.status_code == 200


def test_policy_library_requires_authentication(tmp_path: Path) -> None:
    with TestClient(policy_app(tmp_path, OWNER_ROLE)) as client:
        assert client.get("/api/policies").status_code == 401
        assert client.get("/api/policies/hr78-v3/download").status_code == 401


@pytest.mark.parametrize("role", [OWNER_ROLE, ADMIN_ROLE, MEMBER_ROLE])
def test_every_workspace_role_can_list_and_download_policy_documents(
    tmp_path: Path,
    role: str,
) -> None:
    with TestClient(policy_app(tmp_path, role)) as client:
        sign_in(client)

        catalogue = client.get("/api/policies")
        assert catalogue.status_code == 200
        assert catalogue.json() == [
            {
                "document_id": "hr78-v3",
                "document_type": "Policy",
                "title": "HR.78 Medical & Dental Staff Annual Leave Policy",
                "version": "3",
                "effective_date": "2025-07-01",
                "filename": "HR78-Medical-Dental-Annual-Leave-Policy-v3.pdf",
            },
            {
                "document_id": "hrs09-v1",
                "document_type": "Guidance",
                "title": "HR.S.09 Annual Leave Guidance for Medical & Dental Staff",
                "version": "1",
                "effective_date": "2025-07-01",
                "filename": "HRS09-Medical-Dental-Annual-Leave-Guidance-v1.pdf",
            },
        ]

        download = client.get("/api/policies/hr78-v3/download")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"
        assert download.headers["content-disposition"] == (
            'attachment; filename="HR78-Medical-Dental-Annual-Leave-Policy-v3.pdf"'
        )
        assert download.headers["cache-control"] == "private, no-store"
        assert download.content.startswith(b"%PDF")


def test_policy_library_exposes_only_allowlisted_document_ids(tmp_path: Path) -> None:
    with TestClient(policy_app(tmp_path, OWNER_ROLE)) as client:
        sign_in(client)
        response = client.get("/api/policies/Leave_Template_v0.5_2025-08_to_2026-08.xlsx/download")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "policy_document_not_found"

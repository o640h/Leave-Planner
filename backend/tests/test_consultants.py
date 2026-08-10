"""End-to-end API tests for the first operator workflow."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app
from settings import Settings


def app_for(data_dir: Path) -> FastAPI:
    """Give each test a real migrated SQLite database in its temporary folder."""

    return create_app(
        settings=Settings(environment="test", data_dir=data_dir),
        frontend_dist=data_dir / "no-frontend-build",
    )


def test_create_list_update_and_restart(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        created = client.post(
            "/api/consultants",
            json={"name": "Dr Alex Morgan", "post_title": "Consultant in Radiology"},
        )
        assert created.status_code == 201
        consultant_id = created.json()["id"]

        updated = client.put(
            f"/api/consultants/{consultant_id}",
            json={"name": "Dr Alex Morgan", "post_title": "Clinical Lead"},
        )
        assert updated.json()["post_title"] == "Clinical Lead"

        # A fresh app proves the record came from SQLite rather than process memory.
        with TestClient(app_for(tmp_path)) as client:
            assert client.get("/api/consultants").json() == [
                {
                    "id": consultant_id,
                    "name": "Dr Alex Morgan",
                    "post_title": "Clinical Lead",
                    "archived_at": None,
                }
            ]


def test_directory_is_alphabetical_and_normalizes_blank_post_titles(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        for name in ("Dr Zoe West", "Dr Amy North"):
            response = client.post("/api/consultants", json={"name": name, "post_title": "   "})
            assert response.status_code == 201
            assert response.json()["post_title"] is None

        assert [item["name"] for item in client.get("/api/consultants").json()] == [
            "Dr Amy North",
            "Dr Zoe West",
        ]


def test_api_boundary_rejects_blank_names_and_missing_records(tmp_path: Path) -> None:
    with TestClient(app_for(tmp_path)) as client:
        invalid = client.post("/api/consultants", json={"name": "  ", "post_title": None})
        missing = client.get("/api/consultants/999")

    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "consultant_not_found"

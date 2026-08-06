"""Application smoke tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "development"}


def test_compiled_frontend_is_served_when_present(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Leave Planner</h1>", encoding="utf-8")
    client = TestClient(create_app(frontend_dist=tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Leave Planner" in response.text

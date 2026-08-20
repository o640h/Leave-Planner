"""Application smoke tests."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from main import create_app


class UnavailableEngine:
    """Small failing engine used to prove health reports database loss."""

    def connect(self) -> None:
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    def dispose(self) -> None:
        pass


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "development"}


def test_health_reports_database_unavailability() -> None:
    app = create_app()
    with TestClient(app) as client:
        app.state.database_engine.dispose()
        app.state.database_engine = UnavailableEngine()
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "environment": "development"}


def test_compiled_frontend_is_served_when_present(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Leave Planner</h1>", encoding="utf-8")
    with TestClient(create_app(frontend_dist=tmp_path)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Leave Planner" in response.text

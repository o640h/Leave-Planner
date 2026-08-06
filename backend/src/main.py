"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import create_database_engine
from errors import install_error_handlers
from logging_config import configure_logging
from settings import Settings


def create_app(
    *,
    settings: Settings | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    """Create and configure the Leave Planner API application."""
    runtime = settings or Settings()
    configure_logging(runtime.log_level)
    app = FastAPI(title=runtime.app_name, version="0.1.0")
    app.state.settings = runtime
    app.state.database_engine = create_database_engine(runtime.database_path)
    install_error_handlers(app)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": runtime.environment}

    static_dir = frontend_dist if frontend_dist is not None else runtime.resolved_frontend_dist
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()


def main() -> None:
    """Run the configured local development server."""
    import uvicorn

    runtime = Settings()
    uvicorn.run(
        "main:app",
        host=runtime.host,
        port=runtime.port,
        reload=runtime.environment == "development",
        app_dir=str(Path(__file__).resolve().parent),
    )

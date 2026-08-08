"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from consultants import router as consultant_router
from database import create_database_engine, create_session_factory
from errors import install_error_handlers
from job_plans.router import router as job_plan_router
from leave_years import router as leave_year_router
from logging_config import configure_logging
from migrations import upgrade_database
from settings import Settings


def create_app(
    *,
    settings: Settings | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    """Create and configure the Leave Planner API application."""

    runtime = settings or Settings()
    configure_logging(runtime.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Prepare and close application-owned database resources."""

        upgrade_database(runtime.database_path)
        engine = create_database_engine(runtime.database_path)

        app.state.database_engine = engine
        app.state.session_factory = create_session_factory(engine)

        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=runtime.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = runtime
    install_error_handlers(app)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "environment": runtime.environment,
        }

    app.include_router(consultant_router)
    app.include_router(leave_year_router)
    app.include_router(job_plan_router)

    static_dir = frontend_dist if frontend_dist is not None else runtime.resolved_frontend_dist
    if static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="frontend",
        )

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

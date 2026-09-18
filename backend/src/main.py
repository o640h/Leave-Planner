"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from annual_entitlement.router import router as entitlement_router
from authentication.account_router import router as account_action_router
from authentication.email_delivery import create_email_sender
from authentication.router import router as authentication_router
from carry_forward.router import router as carry_forward_router
from consultant_year_summary import router as consultant_year_summary_router
from consultants import router as consultant_router
from database import create_database_engine, create_session_factory
from errors import install_error_handlers
from http_security import HostedHttpSecurityMiddleware
from job_plans.router import router as job_plan_router
from leave_bookings.router import request_router as leave_request_router
from leave_bookings.router import router as leave_booking_router
from leave_years import router as leave_year_router
from logging_config import configure_logging
from member_workspace.router import router as member_workspace_router
from migrations import require_database_current, upgrade_database
from policy_library.router import router as policy_library_router
from public_holidays.router import settings_router as holiday_settings_router
from public_holidays.router import year_router as holiday_year_router
from recovery import create_startup_backups
from recovery import router as recovery_router
from settings import Settings
from workspaces.dependencies import require_operator_workspace_request
from workspaces.router import router as workspace_router


def create_app(
    *,
    settings: Settings | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    """Create and configure the Leave Planner API application."""

    runtime = settings or Settings()
    configure_logging(runtime.log_level)
    if runtime.environment == "production" and runtime.public_host is None:
        raise RuntimeError("Production requires LEAVE_PLANNER_PUBLIC_ORIGIN")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Prepare and close application-owned database resources."""

        create_startup_backups(runtime)
        if runtime.environment == "production":
            require_database_current(runtime.resolved_database_url)
        else:
            upgrade_database(runtime.resolved_database_url)
        engine = create_database_engine(runtime.resolved_database_url)

        app.state.database_engine = engine
        app.state.session_factory = create_session_factory(engine)

        try:
            yield
        finally:
            app.state.database_engine.dispose()

    app = FastAPI(
        title=runtime.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = runtime
    app.state.email_sender = create_email_sender(runtime)
    app.add_middleware(HostedHttpSecurityMiddleware, settings=runtime)
    if runtime.environment == "production":
        assert runtime.public_host is not None
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[runtime.public_host, "127.0.0.1", "localhost"],
        )
    install_error_handlers(app)

    @app.get("/api/health", tags=["system"])
    def health(request: Request) -> JSONResponse:
        try:
            with request.app.state.database_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "environment": runtime.environment},
            )

        return JSONResponse(
            content={"status": "ok", "environment": runtime.environment},
        )

    app.include_router(authentication_router)
    app.include_router(account_action_router)
    app.include_router(workspace_router)
    app.include_router(member_workspace_router)
    app.include_router(policy_library_router)
    protected = [Depends(require_operator_workspace_request)]
    if runtime.uses_sqlite:
        app.include_router(recovery_router, dependencies=protected)
    app.include_router(consultant_router, dependencies=protected)
    app.include_router(leave_year_router, dependencies=protected)
    app.include_router(job_plan_router, dependencies=protected)
    app.include_router(leave_booking_router, dependencies=protected)
    app.include_router(leave_request_router, dependencies=protected)
    app.include_router(entitlement_router, dependencies=protected)
    app.include_router(carry_forward_router, dependencies=protected)
    app.include_router(consultant_year_summary_router, dependencies=protected)
    app.include_router(holiday_settings_router, dependencies=protected)
    app.include_router(holiday_year_router, dependencies=protected)

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
    """Run the configured development server."""

    import uvicorn

    runtime = Settings()
    uvicorn.run(
        "main:app",
        host=runtime.host,
        port=runtime.port,
        reload=runtime.environment == "development",
        app_dir=str(Path(__file__).resolve().parent),
    )

"""Static acceptance checks for the production container boundary."""

from pathlib import Path
from typing import Any, cast

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def compose_configuration() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        yaml.safe_load((REPOSITORY_ROOT / "deploy" / "compose.yml").read_text(encoding="utf-8")),
    )


def test_database_is_private_persistent_and_resource_limited() -> None:
    configuration = compose_configuration()
    database = configuration["services"]["database"]

    assert database["image"] == "postgres:17.10-alpine3.24"
    assert "ports" not in database
    assert database["networks"] == ["database_network"]
    assert configuration["networks"]["database_network"]["internal"] is True
    assert "postgres_data:/var/lib/postgresql/data" in database["volumes"]
    assert database["mem_limit"] == "1536m"
    assert database["healthcheck"]["test"][0] == "CMD-SHELL"


def test_schema_upgrade_is_a_separate_required_service() -> None:
    services = compose_configuration()["services"]
    migrate = services["migrate"]
    application = services["application"]

    assert migrate["command"] == ["python", "-m", "migrations", "upgrade"]
    assert migrate["restart"] == "no"
    assert migrate["secrets"] == ["migration_database_url"]
    assert application["secrets"] == ["application_database_url", "resend_api_key"]
    assert application["environment"]["LEAVE_PLANNER_EMAIL_PROVIDER"] == "resend"
    assert application["environment"]["LEAVE_PLANNER_EMAIL_FROM"] == (
        "Leave Planner <notifications@merydio.co.uk>"
    )
    assert application["environment"]["LEAVE_PLANNER_REGISTRATION_MODE"] == (
        "${LEAVE_PLANNER_REGISTRATION_MODE:-open}"
    )
    assert application["depends_on"]["migrate"]["condition"] == ("service_completed_successfully")

    initialization = (REPOSITORY_ROOT / "deploy/postgres/init-database.sh").read_text(
        encoding="utf-8"
    )
    assert "leave_planner_application" in initialization
    assert "leave_planner_backup" in initialization
    assert "leave_planner_restore" in initialization
    assert "BYPASSRLS" in initialization
    assert "GRANT USAGE ON SCHEMA public TO leave_planner_backup" in initialization
    assert "GRANT SELECT ON TABLES TO leave_planner_backup" in initialization
    assert "GRANT SELECT ON SEQUENCES TO leave_planner_backup" in initialization

    role_reconciliation = (REPOSITORY_ROOT / "scripts/ConfigureDatabaseRoles.sh").read_text(
        encoding="utf-8"
    )
    assert (
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO leave_planner_backup"
        in role_reconciliation
    )
    assert (
        "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO leave_planner_backup"
        in role_reconciliation
    )
    assert "has_table_privilege" in role_reconciliation


def test_application_image_runs_as_a_read_only_unprivileged_service() -> None:
    configuration = compose_configuration()
    application = configuration["services"]["application"]
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (REPOSITORY_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert application["read_only"] is True
    assert application["cap_drop"] == ["ALL"]
    assert application["security_opt"] == ["no-new-privileges:true"]
    assert application["mem_limit"] == "512m"
    assert application["ports"] == [
        "${LEAVE_PLANNER_BIND_ADDRESS:-127.0.0.1}:${LEAVE_PLANNER_HTTP_PORT:-8080}:8000"
    ]
    assert application["environment"]["LEAVE_PLANNER_PUBLIC_ORIGIN"] == (
        "${LEAVE_PLANNER_PUBLIC_ORIGIN:?Set LEAVE_PLANNER_PUBLIC_ORIGIN in deploy/.env}"
    )
    assert application["healthcheck"]["test"][:3] == ["CMD", "python", "-c"]
    assert "USER 10001:10001" in dockerfile
    assert 'CMD ["python", "-m", "uvicorn"' in dockerfile
    assert '"--no-proxy-headers"' in dockerfile
    assert '"--forwarded-allow-ips", "*"' not in dockerfile
    assert "npm ci" in dockerfile
    assert "uv sync --locked --no-group dev" in dockerfile
    assert "HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf" in dockerfile
    assert "HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf" in dockerfile
    assert "Leave_Template_v0.5_2025-08_to_2026-08.xlsx" not in dockerfile
    assert "!docs/reference/HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf" in dockerignore
    assert (
        "!docs/reference/HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf" in dockerignore
    )
    assert "!docs/reference/Leave_Template_v0.5_2025-08_to_2026-08.xlsx" not in dockerignore
    assert "pywebview" not in dockerfile.lower()
    assert "pyinstaller" not in dockerfile.lower()


def test_release_archive_contains_only_the_policy_documents_needed_by_the_image() -> None:
    release_script = (REPOSITORY_ROOT / "scripts/DeployToNas.ps1").read_text(encoding="utf-8")

    assert "Join-Path $repositoryRoot '.venv'" in release_script
    assert "docs/reference/HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf" in release_script
    assert (
        "docs/reference/HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf"
        in release_script
    )
    assert "docs/reference/Leave_Template_v0.5_2025-08_to_2026-08.xlsx" not in release_script
    assert "'--exclude=.env'" in release_script
    assert "'--exclude=**/.env'" in release_script
    assert '"$PublicOrigin/api/auth/registration"' in release_script


def test_release_supports_a_pristine_postgresql_volume_without_skipping_unknown_data() -> None:
    release_script = (REPOSITORY_ROOT / "scripts/DeployRelease.sh").read_text(encoding="utf-8")

    assert "SELECT version_num FROM alembic_version LIMIT 1" in release_script
    assert "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'" in release_script
    assert "[ \"$application_tables\" = 0 ]" in release_script

"""Resolve application resources from the repository layout."""

from pathlib import Path


def resource_root() -> Path:
    """Return the backend directory containing migrations and configuration."""

    return Path(__file__).resolve().parents[1]


def frontend_distribution() -> Path:
    """Return the compiled React frontend directory."""

    return resource_root().parent / "frontend" / "dist"


def policy_reference_directory() -> Path:
    """Return the private directory containing the bundled policy PDFs."""

    return resource_root().parent / "docs" / "reference"


def alembic_configuration() -> Path:
    """Return the Alembic configuration file."""

    return resource_root() / "alembic.ini"


def migration_directory() -> Path:
    """Return the bundled Alembic migration directory."""

    return resource_root() / "migrations"

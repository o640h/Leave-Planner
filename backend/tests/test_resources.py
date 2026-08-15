"""Resource-path tests for source and packaged application layouts."""

from pathlib import Path

from pytest import MonkeyPatch

import resources


def test_source_resources_resolve_from_the_repository() -> None:
    """Development runs read the frontend and Alembic files from the repository."""

    backend_root = Path(resources.__file__).resolve().parents[1]
    project_root = backend_root.parent

    assert resources.resource_root() == backend_root
    assert resources.frontend_distribution() == project_root / "frontend" / "dist"
    assert resources.alembic_configuration() == backend_root / "alembic.ini"
    assert resources.migration_directory() == backend_root / "migrations"


def test_packaged_resources_resolve_beside_the_frozen_modules(
    monkeypatch: MonkeyPatch,
) -> None:
    """PyInstaller runs read bundled data relative to the extracted module tree."""

    monkeypatch.setattr(resources, "is_packaged", lambda: True)
    bundle_root = Path(resources.__file__).resolve().parent

    assert resources.resource_root() == bundle_root
    assert resources.frontend_distribution() == bundle_root / "frontend" / "dist"
    assert resources.alembic_configuration() == bundle_root / "alembic.ini"
    assert resources.migration_directory() == bundle_root / "migrations"

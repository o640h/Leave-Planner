"""Portable SQLAlchemy engine and transaction foundations."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base for future persisted domain models."""


def sqlite_url(database_path: Path) -> URL:
    return URL.create("sqlite+pysqlite", database=str(database_path))


def database_url(value: str | URL) -> URL:
    """Parse one supported SQLAlchemy database URL without connecting."""

    url = make_url(value) if isinstance(value, str) else value
    if url.drivername not in {"sqlite+pysqlite", "postgresql+psycopg"}:
        raise ValueError("Database URL must use sqlite+pysqlite or postgresql+psycopg")
    return url


def create_database_engine(value: str | URL) -> Engine:
    """Create an engine with safeguards appropriate to its database backend."""

    url = database_url(value)
    engine = create_engine(url, future=True, pool_pre_ping=url.get_backend_name() == "postgresql")

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(connection: sqlite3.Connection, _record: object) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on failure."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

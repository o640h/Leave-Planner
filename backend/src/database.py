"""SQLite and SQLAlchemy foundations."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base for future persisted domain models."""


def sqlite_url(database_path: Path) -> URL:
    return URL.create("sqlite+pysqlite", database=str(database_path))


def create_database_engine(database_path: Path) -> Engine:
    """Create a SQLite engine with local durability and integrity safeguards."""
    engine = create_engine(sqlite_url(database_path), future=True)

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

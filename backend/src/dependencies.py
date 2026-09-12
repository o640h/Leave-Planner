"""FastAPI dependencies shared by API routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from database import session_scope


def get_database_session(request: Request) -> Iterator[Session]:
    """Provide one transactional database session per API request."""

    factory: sessionmaker[Session] = request.app.state.session_factory

    with session_scope(factory) as session:
        yield session


# Finish the database transaction before the response is sent. A request-scoped
# dependency can commit after response headers (including the new session cookie)
# have gone to the browser, allowing the browser's immediate follow-up request to
# briefly miss a session created during login.
DatabaseSession = Annotated[Session, Depends(get_database_session, scope="function")]

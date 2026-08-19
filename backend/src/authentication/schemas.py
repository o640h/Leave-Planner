"""Authentication API contracts."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class AuthenticatedUserRead(BaseModel):
    id: int
    display_name: str


class SessionRead(BaseModel):
    authenticated: bool
    user: AuthenticatedUserRead | None = None

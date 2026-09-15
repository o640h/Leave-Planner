"""Authentication API contracts."""

from pydantic import BaseModel, EmailStr, Field

from workspaces.schemas import WorkspaceContextRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class AuthenticatedUserRead(BaseModel):
    public_id: str
    display_name: str
    display_email: str


class SessionRead(BaseModel):
    authenticated: bool
    user: AuthenticatedUserRead | None = None
    workspace: WorkspaceContextRead | None = None

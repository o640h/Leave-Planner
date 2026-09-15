"""Authentication API contracts."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from workspaces.schemas import WorkspaceContextRead

from .passwords import MINIMUM_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class EmailActionRequest(BaseModel):
    email: EmailStr


class RegistrationRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=MINIMUM_PASSWORD_LENGTH, max_length=1024)


class RegistrationConfigurationRead(BaseModel):
    mode: Literal["closed", "invitation_only", "open"]


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class PasswordResetRequest(TokenRequest):
    password: str = Field(min_length=MINIMUM_PASSWORD_LENGTH, max_length=1024)


class EmailChangeRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class MessageRead(BaseModel):
    message: str


class DevelopmentEmailRead(BaseModel):
    id: str
    recipient: str
    subject: str
    text: str


class AuthenticatedUserRead(BaseModel):
    public_id: str
    display_name: str
    display_email: str


class SessionRead(BaseModel):
    authenticated: bool
    user: AuthenticatedUserRead | None = None
    workspace: WorkspaceContextRead | None = None

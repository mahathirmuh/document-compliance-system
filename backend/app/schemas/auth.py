"""Authentication request and response schemas."""

from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import ApiSchema
from app.schemas.user import UserResponse


class LoginRequest(ApiSchema):
    """Email-and-password login credentials."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class TokenRefreshRequest(ApiSchema):
    """Refresh-token rotation payload."""

    refresh_token: str = Field(min_length=1, max_length=4096)


class LogoutRequest(ApiSchema):
    """Refresh token identifying the session to revoke."""

    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenResponse(ApiSchema):
    """Access/refresh credentials plus the current authorization context."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)
    user: UserResponse
    permissions: list[str]


class CurrentUserResponse(ApiSchema):
    """Current user and backend-authoritative permission strings."""

    user: UserResponse
    permissions: list[str]

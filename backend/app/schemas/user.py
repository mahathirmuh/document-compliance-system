"""User administration and current-user API schemas."""

from uuid import UUID

from pydantic import EmailStr

from app.core.authorization import UserRole
from app.schemas.base import ApiSchema


class UserResponse(ApiSchema):
    """Client-safe user representation; never contains a password hash."""

    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    department_id: UUID | None
    is_active: bool

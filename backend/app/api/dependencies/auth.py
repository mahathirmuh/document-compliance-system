"""Authentication, active-user, role, and permission dependencies."""

from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Permission, UserRole, get_permissions
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.database.session import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth.auth_service import AuthService, RequestMetadata
from app.services.auth.password_service import PasswordService
from app.services.auth.token_service import TokenService

bearer_scheme = HTTPBearer(auto_error=False)


def get_password_service() -> PasswordService:
    """Provide the stateless password service."""
    return PasswordService()


def get_token_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenService:
    """Provide a token service bound to validated environment settings."""
    return TokenService(settings)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    password_service: Annotated[
        PasswordService, Depends(get_password_service)
    ],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    """Compose the authentication service at the API boundary."""
    return AuthService(
        session,
        settings,
        password_service,
        token_service,
    )


def get_request_metadata(request: Request) -> RequestMetadata:
    """Extract audit metadata without trusting forwarding headers."""
    return RequestMetadata(
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> User:
    """Resolve an access token to a non-deleted database user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Bearer access token is required.")

    claims = token_service.decode_token(
        credentials.credentials,
        expected_type="access",
    )
    try:
        user_id = UUID(str(claims.get("sub")))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Access token subject is invalid.") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("Access token user no longer exists.")
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Reject access tokens whose user has since been disabled."""
    if not current_user.is_active:
        raise AuthenticationError("User account is inactive.")
    return current_user


AuthDependency = Callable[..., Coroutine[Any, Any, User]]


def require_roles(*roles: UserRole) -> AuthDependency:
    """Require at least one allowed role for a protected endpoint."""
    allowed_roles = frozenset(roles)

    async def role_dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if (
            not current_user.is_superuser
            and current_user.role not in allowed_roles
        ):
            raise AuthorizationError()
        return current_user

    return role_dependency


def require_permissions(*permissions: Permission | str) -> AuthDependency:
    """Require every named permission using the single backend role mapping."""
    required = {
        permission.value if isinstance(permission, Enum) else permission
        for permission in permissions
    }

    async def permission_dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        assigned = set(
            get_permissions(
                current_user.role,
                is_superuser=current_user.is_superuser,
            )
        )
        if not required.issubset(assigned):
            raise AuthorizationError()
        return current_user

    return permission_dependency

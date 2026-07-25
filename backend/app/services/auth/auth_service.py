"""Authentication use cases and transaction boundaries."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, get_permissions
from app.core.config import Settings
from app.core.exceptions import AccountLockedError, AuthenticationError
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth.password_service import PasswordService
from app.services.auth.token_service import TokenService
from app.utils.datetime import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    """Security-relevant request metadata safe to persist in audit records."""

    ip_address: str | None
    user_agent: str | None


class AuthService:
    """Coordinate repositories and security primitives for authentication."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        password_service: PasswordService,
        token_service: TokenService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._passwords = password_service
        self._tokens = token_service
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._audit_logs = AuditLogRepository(session)

    async def login(
        self,
        payload: LoginRequest,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        """Authenticate a user, enforce locking, and start a token session."""
        email = str(payload.email).strip().lower()
        now = utc_now()
        user = await self._users.get_by_email(email, for_update=True)

        if user is None:
            self._passwords.consume_dummy_verification(payload.password)
            await self._record_login_failure(None, metadata)
            await self._session.commit()
            raise AuthenticationError("Email or password is invalid.")

        if self._is_locked(user, now):
            await self._record_login_failure(user, metadata)
            await self._session.commit()
            raise AccountLockedError()

        if user.locked_until is not None:
            user.locked_until = None
            user.failed_login_attempts = 0

        password_is_valid, replacement_hash = self._passwords.verify_and_update(
            payload.password,
            user.password_hash,
        )
        if not user.is_active or not password_is_valid:
            user.failed_login_attempts += 1
            should_lock = (
                user.failed_login_attempts
                >= self._settings.max_login_attempts
            )
            if should_lock:
                user.locked_until = now + timedelta(
                    minutes=self._settings.account_lock_minutes
                )

            await self._record_login_failure(user, metadata)
            if should_lock:
                await self._audit_logs.create(
                    user_id=user.id,
                    action=AuditAction.ACCOUNT_LOCKED,
                    entity_type="user",
                    entity_id=user.id,
                    description="Account locked after repeated login failures.",
                    ip_address=metadata.ip_address,
                    user_agent=metadata.user_agent,
                )
            await self._session.commit()
            if should_lock:
                raise AccountLockedError()
            raise AuthenticationError("Email or password is invalid.")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        if replacement_hash is not None:
            user.password_hash = replacement_hash
        response = await self._issue_token_pair(user, metadata)
        await self._audit_logs.create(
            user_id=user.id,
            action=AuditAction.LOGIN_SUCCESS,
            entity_type="user",
            entity_id=user.id,
            description="User login succeeded.",
            ip_address=metadata.ip_address,
            user_agent=metadata.user_agent,
        )
        await self._session.commit()
        return response

    async def refresh(
        self,
        raw_refresh_token: str,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        """Rotate a valid refresh token and revoke the consumed token."""
        claims = self._tokens.decode_token(
            raw_refresh_token,
            expected_type="refresh",
        )
        user_id = self._subject_as_uuid(claims)
        token_hash = self._tokens.hash_token(raw_refresh_token)
        stored_token = await self._refresh_tokens.get_by_hash(
            token_hash,
            for_update=True,
        )
        now = utc_now()

        if (
            stored_token is None
            or stored_token.user_id != user_id
            or stored_token.revoked_at is not None
            or ensure_utc(stored_token.expires_at) <= now
        ):
            raise AuthenticationError(
                "Refresh token is invalid or has been revoked."
            )

        user = await self._users.get_by_id(user_id, for_update=True)
        if user is None or not user.is_active:
            await self._refresh_tokens.revoke(stored_token, revoked_at=now)
            await self._session.commit()
            raise AuthenticationError(
                "Refresh token is invalid or has been revoked."
            )

        await self._refresh_tokens.revoke(stored_token, revoked_at=now)
        response = await self._issue_token_pair(user, metadata)
        await self._audit_logs.create(
            user_id=user.id,
            action=AuditAction.TOKEN_REFRESH,
            entity_type="user",
            entity_id=user.id,
            description="Refresh token rotated successfully.",
            ip_address=metadata.ip_address,
            user_agent=metadata.user_agent,
        )
        await self._session.commit()
        return response

    async def logout(
        self,
        raw_refresh_token: str,
        metadata: RequestMetadata,
    ) -> None:
        """Revoke one refresh-token session.

        A signed token that is already absent or revoked is treated
        idempotently so clients can always clear their local session.
        """
        claims = self._tokens.decode_token(
            raw_refresh_token,
            expected_type="refresh",
        )
        user_id = self._subject_as_uuid(claims)
        stored_token = await self._refresh_tokens.get_by_hash(
            self._tokens.hash_token(raw_refresh_token),
            for_update=True,
        )
        now = utc_now()
        if stored_token is not None and stored_token.user_id == user_id:
            await self._refresh_tokens.revoke(stored_token, revoked_at=now)

        user = await self._users.get_by_id(user_id)
        if user is not None:
            await self._audit_logs.create(
                user_id=user.id,
                action=AuditAction.LOGOUT,
                entity_type="user",
                entity_id=user.id,
                description="User logged out.",
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
            )
        await self._session.commit()

    def current_user(self, user: User) -> CurrentUserResponse:
        """Build the public user and permission representation."""
        return CurrentUserResponse(
            user=UserResponse.model_validate(user),
            permissions=get_permissions(
                user.role,
                is_superuser=user.is_superuser,
            ),
        )

    async def revoke_all_sessions(self, user_id: UUID) -> int:
        """Revoke all sessions for future user-administration workflows."""
        revoked = await self._refresh_tokens.revoke_all_for_user(
            user_id,
            revoked_at=utc_now(),
        )
        await self._session.commit()
        return revoked

    async def _issue_token_pair(
        self,
        user: User,
        metadata: RequestMetadata,
    ) -> TokenResponse:
        access_token = self._tokens.create_access_token(user)
        refresh_token = self._tokens.create_refresh_token(user)
        refresh_claims = self._tokens.decode_token(
            refresh_token,
            expected_type="refresh",
        )
        expires_at = datetime.fromtimestamp(
            int(refresh_claims["exp"]),
            tz=UTC,
        )
        await self._refresh_tokens.add(
            user_id=user.id,
            token_hash=self._tokens.hash_token(refresh_token),
            expires_at=expires_at,
            created_by_ip=metadata.ip_address,
            user_agent=metadata.user_agent,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self._settings.jwt_access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
            permissions=get_permissions(
                user.role,
                is_superuser=user.is_superuser,
            ),
        )

    async def _record_login_failure(
        self,
        user: User | None,
        metadata: RequestMetadata,
    ) -> None:
        await self._audit_logs.create(
            user_id=user.id if user is not None else None,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            entity_id=user.id if user is not None else None,
            description="User login failed.",
            ip_address=metadata.ip_address,
            user_agent=metadata.user_agent,
        )

    @staticmethod
    def _is_locked(user: User, now: datetime) -> bool:
        return (
            user.locked_until is not None
            and ensure_utc(user.locked_until) > now
        )

    @staticmethod
    def _subject_as_uuid(claims: dict[str, object]) -> UUID:
        subject = claims.get("sub")
        try:
            return UUID(str(subject))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError(
                "Token subject is invalid."
            ) from exc

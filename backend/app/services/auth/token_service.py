"""JWT access/refresh creation, validation, and at-rest token hashing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from jwt.types import Options

from app.core.authorization import UserRole
from app.core.config import Settings
from app.core.exceptions import AuthenticationError

if TYPE_CHECKING:
    from app.models.user import User

TokenType = Literal["access", "refresh"]


class TokenService:
    """Issue and verify signed JWTs without owning session persistence."""

    def __init__(self, settings: Settings) -> None:
        secret_value = settings.jwt_secret_key
        self._secret_key = (
            secret_value.get_secret_value()
            if hasattr(secret_value, "get_secret_value")
            else str(secret_value)
        )
        if not self._secret_key:
            raise ValueError("JWT secret key must not be empty.")

        self._algorithm = settings.jwt_algorithm
        self._access_token_lifetime = timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
        self._refresh_token_lifetime = timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    @property
    def access_token_expires_seconds(self) -> int:
        """Configured access-token lifetime for API response metadata."""

        return int(self._access_token_lifetime.total_seconds())

    def create_access_token(
        self,
        user: User,
        *,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a short-lived access JWT for one active user principal."""

        role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
        return self._create_token(
            subject=str(user.id),
            token_type="access",
            lifetime=expires_delta or self._access_token_lifetime,
            additional_claims={
                "email": user.email,
                "role": role.value,
            },
        )

    def create_refresh_token(
        self,
        user: User,
        *,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a long-lived refresh JWT suitable for server-side rotation."""

        return self._create_token(
            subject=str(user.id),
            token_type="refresh",
            lifetime=expires_delta or self._refresh_token_lifetime,
        )

    def rotate_refresh_token(
        self,
        token: str,
        user: User,
    ) -> tuple[str, str]:
        """Validate a refresh JWT and create its replacement token pair.

        The caller remains responsible for atomically revoking/storing hashes
        in the database; AuthService supplies that transaction boundary.
        """
        claims = self.decode_token(token, expected_type="refresh")
        if claims.get("sub") != str(user.id):
            raise AuthenticationError("Refresh token subject is invalid.")
        return (
            self.create_access_token(user),
            self.create_refresh_token(user),
        )

    def revoke_refresh_token(self, token: str) -> str:
        """Validate a refresh JWT and return its persistence lookup hash."""
        self.decode_token(token, expected_type="refresh")
        return self.hash_token(token)

    def decode_token(
        self,
        token: str,
        expected_type: TokenType | None = None,
    ) -> dict[str, Any]:
        """Verify a JWT and return its claims or raise a safe auth error."""

        if not token:
            raise AuthenticationError("Token is invalid.")

        options: Options = {
            "require": ["sub", "type", "iat", "nbf", "exp", "jti"],
            "verify_aud": False,
            "verify_iss": False,
        }
        try:
            claims = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options=options,
            )
            token_type = claims.get("type")
            if token_type not in ("access", "refresh"):
                raise InvalidTokenError("Unknown token type.")
            if expected_type is not None and token_type != expected_type:
                raise InvalidTokenError("Unexpected token type.")
            if token_type == "access":
                UserRole(claims.get("role"))
                if not isinstance(claims.get("email"), str):
                    raise InvalidTokenError("Access token email is missing.")
            return claims
        except ExpiredSignatureError as exc:
            raise AuthenticationError("Token has expired.") from exc
        except (InvalidTokenError, TypeError, ValueError) as exc:
            raise AuthenticationError("Token is invalid.") from exc

    @staticmethod
    def hash_token(token: str) -> str:
        """Return the deterministic SHA-256 digest stored for refresh tokens."""

        if not token:
            raise ValueError("Token must not be empty.")
        return sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def verify_token_hash(cls, token: str, expected_hash: str) -> bool:
        """Constant-time comparison for an incoming token and stored digest."""

        if not token or not expected_hash:
            return False
        return compare_digest(cls.hash_token(token), expected_hash)

    @staticmethod
    def get_expiration(claims: dict[str, Any]) -> datetime:
        """Return the token expiration as a timezone-aware UTC datetime."""

        expiration = claims.get("exp")
        if isinstance(expiration, bool) or not isinstance(expiration, (int, float)):
            raise AuthenticationError("Token is invalid.")
        try:
            return datetime.fromtimestamp(expiration, tz=UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise AuthenticationError("Token is invalid.") from exc

    def _create_token(
        self,
        *,
        subject: str,
        token_type: TokenType,
        lifetime: timedelta,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": subject,
            "type": token_type,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "jti": str(uuid4()),
        }
        if additional_claims:
            payload.update(additional_claims)
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

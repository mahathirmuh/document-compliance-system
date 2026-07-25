"""Persistence operations for refresh-token sessions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """Store only deterministic hashes of refresh JWTs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(
        self,
        token_hash: str,
        *,
        for_update: bool = False,
    ) -> RefreshToken | None:
        statement = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        created_by_ip: str | None,
        user_agent: str | None,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by_ip=created_by_ip,
            user_agent=user_agent,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def revoke(
        self,
        refresh_token: RefreshToken,
        *,
        revoked_at: datetime,
    ) -> None:
        if refresh_token.revoked_at is None:
            refresh_token.revoked_at = revoked_at
            await self._session.flush()

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        *,
        revoked_at: datetime,
    ) -> int:
        result = await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return int(result.rowcount or 0)

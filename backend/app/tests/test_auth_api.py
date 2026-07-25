"""Authentication API integration tests on an isolated async database."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction, UserRole
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth.token_service import TokenService

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


async def _load_user(
    session_factory: TestSessionFactory,
    email: str = "user@example.com",
) -> User:
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one()


async def _load_audits(
    session_factory: TestSessionFactory,
) -> list[AuditLog]:
    async with session_factory() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at)
        )
        return list(result.scalars())


@pytest.mark.asyncio
async def test_login_success_returns_camel_case_contract_and_audit(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
) -> None:
    await create_user()

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "USER@example.com", "password": "Valid123"},
        headers={"user-agent": "pytest-agent"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Login successful."
    assert payload["data"]["tokenType"] == "bearer"
    assert payload["data"]["expiresIn"] == 900
    assert payload["data"]["accessToken"]
    assert payload["data"]["refreshToken"]
    assert payload["data"]["user"] == {
        "id": payload["data"]["user"]["id"],
        "name": "Test User",
        "email": "user@example.com",
        "role": "VIEWER",
        "departmentId": None,
        "isActive": True,
    }
    assert payload["data"]["permissions"] == [
        "dashboard:view",
        "documents:download",
        "documents:view",
    ]
    assert "passwordHash" not in str(payload)

    user = await _load_user(session_factory)
    assert user.last_login_at is not None
    assert user.failed_login_attempts == 0
    audits = await _load_audits(session_factory)
    assert [audit.action for audit in audits] == [AuditAction.LOGIN_SUCCESS]
    assert audits[0].user_agent == "pytest-agent"


@pytest.mark.asyncio
async def test_unknown_email_is_rejected_and_audited(
    api_client: AsyncClient,
    session_factory: TestSessionFactory,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "Wrong123"},
    )

    assert response.status_code == 401
    assert (
        response.json()["errors"][0]["message"]
        == "Email or password is invalid."
    )
    audits = await _load_audits(session_factory)
    assert audits[0].action is AuditAction.LOGIN_FAILED
    assert audits[0].user_id is None


@pytest.mark.asyncio
async def test_wrong_password_increments_failed_attempts(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
) -> None:
    await create_user()

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Wrong123"},
    )

    assert response.status_code == 401
    assert (await _load_user(session_factory)).failed_login_attempts == 1
    assert (await _load_audits(session_factory))[0].action is AuditAction.LOGIN_FAILED


@pytest.mark.asyncio
async def test_inactive_user_is_rejected(
    api_client: AsyncClient,
    create_user: UserFactory,
) -> None:
    await create_user(is_active=False)

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_account_locks_at_configured_threshold(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
) -> None:
    await create_user()
    statuses = []
    for _ in range(3):
        response = await api_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "Wrong123"},
        )
        statuses.append(response.status_code)

    locked_response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )

    assert statuses == [401, 401, 429]
    assert locked_response.status_code == 429
    user = await _load_user(session_factory)
    assert user.failed_login_attempts == 3
    assert user.locked_until is not None
    actions = [audit.action for audit in await _load_audits(session_factory)]
    assert AuditAction.ACCOUNT_LOCKED in actions


@pytest.mark.asyncio
async def test_successful_login_resets_previous_failures(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
) -> None:
    await create_user(failed_login_attempts=2)

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )

    assert response.status_code == 200
    user = await _load_user(session_factory)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_rejects_reuse(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
    token_service: TokenService,
) -> None:
    await create_user()
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )
    old_token = login.json()["data"]["refreshToken"]

    refresh = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": old_token},
    )
    reuse = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": old_token},
    )

    assert refresh.status_code == 200
    assert refresh.json()["data"]["refreshToken"] != old_token
    assert reuse.status_code == 401
    async with session_factory() as session:
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_service.hash_token(old_token)
            )
        )
        stored = result.scalar_one()
        assert stored.revoked_at is not None
    actions = [audit.action for audit in await _load_audits(session_factory)]
    assert AuditAction.TOKEN_REFRESH in actions


@pytest.mark.asyncio
async def test_invalid_refresh_token_is_rejected(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": "not-a-valid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_returns_user_for_access_token(
    api_client: AsyncClient,
    create_user: UserFactory,
) -> None:
    await create_user(role=UserRole.REVIEWER)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )
    access_token = login.json()["data"]["accessToken"]

    response = await api_client.get(
        "/api/v1/auth/me",
        headers={"authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["role"] == "REVIEWER"
    assert "findings:resolve" in response.json()["data"]["permissions"]


@pytest.mark.asyncio
async def test_auth_me_requires_access_token(
    api_client: AsyncClient,
    create_user: UserFactory,
) -> None:
    user = await create_user()
    no_token = await api_client.get("/api/v1/auth/me")

    assert no_token.status_code == 401

    # A refresh JWT must never be accepted as an access token.
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Valid123"},
    )
    refresh = login.json()["data"]["refreshToken"]
    wrong_type = await api_client.get(
        "/api/v1/auth/me",
        headers={"authorization": f"Bearer {refresh}"},
    )
    assert wrong_type.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token_and_audits(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
    token_service: TokenService,
) -> None:
    await create_user()
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )
    refresh_token = login.json()["data"]["refreshToken"]

    response = await api_client.post(
        "/api/v1/auth/logout",
        json={"refreshToken": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    async with session_factory() as session:
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash
                == token_service.hash_token(refresh_token)
            )
        )
        assert result.scalar_one().revoked_at is not None
    assert AuditAction.LOGOUT in [
        audit.action for audit in await _load_audits(session_factory)
    ]


@pytest.mark.asyncio
async def test_audit_and_refresh_storage_never_contain_raw_secrets(
    api_client: AsyncClient,
    create_user: UserFactory,
    session_factory: TestSessionFactory,
) -> None:
    await create_user()
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "Valid123"},
    )
    raw_refresh = response.json()["data"]["refreshToken"]

    async with session_factory() as session:
        refresh_rows = list((await session.execute(select(RefreshToken))).scalars())
        audit_rows = list((await session.execute(select(AuditLog))).scalars())

    assert raw_refresh not in {row.token_hash for row in refresh_rows}
    assert all(len(row.token_hash) == 64 for row in refresh_rows)
    serialized_audits = repr(
        [
            (
                row.description,
                row.old_values_json,
                row.new_values_json,
            )
            for row in audit_rows
        ]
    )
    assert "Valid123" not in serialized_audits
    assert raw_refresh not in serialized_audits

"""Canonical permission mapping and guard tests."""

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies.auth import (
    get_current_active_user,
    require_permissions,
    require_roles,
)
from app.core.authorization import Permission, UserRole, get_permissions
from app.core.exception_handlers import register_exception_handlers
from app.models.user import User


def _principal(role: UserRole) -> User:
    return User(
        name="RBAC User",
        email=f"{role.value.lower()}@example.com",
        password_hash="not-used",
        role=role,
        is_active=True,
        is_superuser=False,
    )


def test_permission_mapping_matches_centralized_role_contract() -> None:
    expected_permissions = {
        UserRole.SUPER_ADMIN: {
            permission.value for permission in Permission
        },
        UserRole.DOCUMENT_CONTROLLER: {
            "dashboard:view",
            "documents:view",
            "documents:create",
            "documents:update",
            "documents:archive",
            "documents:restore",
            "documents:export",
            "documents:import",
            "documents:view_all_departments",
            "documents:manage_revisions",
            "documents:validate",
            "documents:assign_reviewer",
            "findings:view",
            "findings:update",
            "findings:resolve",
            "master_data:view",
            "reports:view",
            "reports:export",
        },
        UserRole.REVIEWER: {
            "dashboard:view",
            "documents:view",
            "findings:view",
            "findings:update",
            "findings:resolve",
            "reports:view",
        },
        UserRole.DEPARTMENT_USER: {
            "dashboard:view",
            "documents:view",
            "documents:create",
            "documents:update",
            "findings:view",
        },
        UserRole.AUDITOR: {
            "dashboard:view",
            "documents:view",
            "documents:export",
            "documents:view_all_departments",
            "findings:view",
            "reports:view",
            "reports:export",
            "audit_logs:view",
        },
        UserRole.VIEWER: {
            "dashboard:view",
            "documents:view",
        },
    }

    for role, expected in expected_permissions.items():
        assert set(get_permissions(role)) == expected


@pytest.mark.asyncio
async def test_allowed_role_can_access_guarded_endpoint() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/review")
    async def review_route(
        _: User = Depends(require_roles(UserRole.REVIEWER)),
    ) -> dict[str, bool]:
        return {"allowed": True}

    test_app.dependency_overrides[get_current_active_user] = lambda: _principal(
        UserRole.REVIEWER
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.get("/review")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_disallowed_role_receives_403() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/users")
    async def users_route(
        _: User = Depends(require_permissions(Permission.USERS_VIEW)),
    ) -> dict[str, bool]:
        return {"allowed": True}

    test_app.dependency_overrides[get_current_active_user] = lambda: _principal(
        UserRole.VIEWER
    )
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.get("/users")

    assert response.status_code == 403
    assert response.json()["success"] is False

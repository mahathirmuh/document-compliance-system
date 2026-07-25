"""Canonical permission mapping and guard tests."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

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
            "documents:upload",
            "documents:download",
            "documents:replace_file",
            "documents:delete_file",
            "documents:batch_upload",
            "documents:view_file_history",
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
            "documents:download",
            "documents:view_file_history",
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
            "documents:upload",
            "documents:download",
            "documents:view_file_history",
            "findings:view",
        },
        UserRole.AUDITOR: {
            "dashboard:view",
            "documents:view",
            "documents:export",
            "documents:view_all_departments",
            "documents:download",
            "documents:view_file_history",
            "findings:view",
            "reports:view",
            "reports:export",
            "audit_logs:view",
        },
        UserRole.VIEWER: {
            "dashboard:view",
            "documents:view",
            "documents:download",
        },
    }

    for role, expected in expected_permissions.items():
        assert set(get_permissions(role)) == expected

    assert "documents:replace_file" not in get_permissions(
        UserRole.DEPARTMENT_USER
    )
    assert "documents:delete_file" not in get_permissions(
        UserRole.DEPARTMENT_USER
    )
    assert "documents:upload" not in get_permissions(UserRole.AUDITOR)
    assert "documents:view_file_history" not in get_permissions(
        UserRole.VIEWER
    )


@pytest.mark.asyncio
async def test_allowed_role_can_access_guarded_endpoint() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/review")
    async def review_route(
        _: Annotated[
            User,
            Depends(require_roles(UserRole.REVIEWER)),
        ],
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
        _: Annotated[
            User,
            Depends(require_permissions(Permission.USERS_VIEW)),
        ],
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

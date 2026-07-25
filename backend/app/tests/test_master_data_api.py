"""Phase 3 master-data API integration tests."""

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction, UserRole
from app.models.audit_log import AuditLog
from app.services.auth.token_service import TokenService

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


async def _admin_headers(
    create_user: UserFactory,
    token_service: TokenService,
) -> dict[str, str]:
    user = await create_user(
        email="master-admin@example.com",
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
    )
    return {"Authorization": f"Bearer {token_service.create_access_token(user)}"}


@pytest.mark.asyncio
async def test_department_crud_search_pagination_and_audit(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    headers = await _admin_headers(create_user, token_service)

    created = await api_client.post(
        "/api/v1/master-data/departments",
        headers=headers,
        json={
            "code": "  ict_ops ",
            "name": "  ICT Operations ",
            "description": " Operations ",
        },
    )
    assert created.status_code == 201, created.text
    department = created.json()["data"]
    assert department["code"] == "ICT_OPS"
    assert department["name"] == "ICT Operations"

    duplicate = await api_client.post(
        "/api/v1/master-data/departments",
        headers=headers,
        json={"code": "ICT_OPS", "name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["errors"][0]["field"] == "code"

    listed = await api_client.get(
        "/api/v1/master-data/departments",
        headers=headers,
        params={"search": "operations", "page": 1, "pageSize": 10},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["totalItems"] == 1
    assert listed.json()["data"]["items"][0]["id"] == department["id"]

    bypass = await api_client.put(
        f"/api/v1/master-data/departments/{department['id']}",
        headers=headers,
        json={"isActive": False},
    )
    assert bypass.status_code == 400
    assert bypass.json()["errors"][0]["field"] == "isActive"
    unchanged = await api_client.get(
        f"/api/v1/master-data/departments/{department['id']}",
        headers=headers,
    )
    assert unchanged.json()["data"]["isActive"] is True

    updated = await api_client.put(
        f"/api/v1/master-data/departments/{department['id']}",
        headers=headers,
        json={"name": "Infrastructure Operations"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Infrastructure Operations"

    deactivated = await api_client.patch(
        f"/api/v1/master-data/departments/{department['id']}/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["isActive"] is False

    async with session_factory() as session:
        actions = list(
            (
                await session.scalars(
                    select(AuditLog.action).order_by(AuditLog.created_at)
                )
            ).all()
        )
    assert actions == [
        AuditAction.CREATE_DEPARTMENT,
        AuditAction.UPDATE_DEPARTMENT,
        AuditAction.DEACTIVATE_DEPARTMENT,
    ]


@pytest.mark.asyncio
async def test_master_data_permission_is_backend_enforced(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    viewer = await create_user(role=UserRole.VIEWER)
    headers = {
        "Authorization": f"Bearer {token_service.create_access_token(viewer)}"
    }
    assert (
        await api_client.get(
            "/api/v1/master-data/departments",
            headers=headers,
        )
    ).status_code == 403
    assert (
        await api_client.post(
            "/api/v1/master-data/departments",
            headers=headers,
            json={"code": "OPS", "name": "Operations"},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_sections_require_active_department_and_unique_scoped_code(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _admin_headers(create_user, token_service)

    async def department(code: str) -> dict[str, Any]:
        response = await api_client.post(
            "/api/v1/master-data/departments",
            headers=headers,
            json={"code": code, "name": f"{code} Department"},
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    first_department = await department("DPT_A")
    second_department = await department("DPT_B")
    payload = {
        "departmentId": first_department["id"],
        "code": "SEC",
        "name": "Section",
    }
    first = await api_client.post(
        "/api/v1/master-data/sections",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["department"]["code"] == "DPT_A"

    duplicate = await api_client.post(
        "/api/v1/master-data/sections",
        headers=headers,
        json=payload,
    )
    assert duplicate.status_code == 409

    other_department = await api_client.post(
        "/api/v1/master-data/sections",
        headers=headers,
        json={**payload, "departmentId": second_department["id"]},
    )
    assert other_department.status_code == 201, other_department.text

    await api_client.patch(
        f"/api/v1/master-data/departments/{second_department['id']}/deactivate",
        headers=headers,
    )
    inactive = await api_client.post(
        "/api/v1/master-data/sections",
        headers=headers,
        json={
            "departmentId": second_department["id"],
            "code": "NEW",
            "name": "New",
        },
    )
    assert inactive.status_code == 400
    assert inactive.json()["errors"][0]["field"] == "departmentId"

    filtered = await api_client.get(
        "/api/v1/master-data/sections",
        headers=headers,
        params={"departmentId": first_department["id"]},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["data"]["totalItems"] == 1


@pytest.mark.asyncio
async def test_document_type_and_status_rules(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _admin_headers(create_user, token_service)
    document_type = await api_client.post(
        "/api/v1/master-data/document-types",
        headers=headers,
        json={
            "code": "sop",
            "name": "Standard Operating Procedure",
            "category": "PROCEDURE",
            "requiresSection": True,
        },
    )
    assert document_type.status_code == 201, document_type.text
    assert document_type.json()["data"]["code"] == "SOP"
    assert (
        await api_client.patch(
            "/api/v1/master-data/document-types/"
            f"{document_type.json()['data']['id']}/deactivate",
            headers=headers,
        )
    ).status_code == 200

    inactive_rule = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            "code": "INACTIVE-RULE",
            "name": "Inactive Rule",
            "isDefault": False,
        },
    )
    assert inactive_rule.status_code == 201, inactive_rule.text
    assert (
        await api_client.patch(
            "/api/v1/master-data/validation-rules/"
            f"{inactive_rule.json()['data']['id']}/deactivate",
            headers=headers,
        )
    ).status_code == 200
    inactive_default = await api_client.post(
        "/api/v1/master-data/document-types",
        headers=headers,
        json={
            "code": "WIN",
            "name": "Work Instruction",
            "category": "PROCEDURE",
            "defaultValidationRuleId": inactive_rule.json()["data"]["id"],
        },
    )
    assert inactive_default.status_code == 400
    assert (
        inactive_default.json()["errors"][0]["field"]
        == "defaultValidationRuleId"
    )

    draft = await api_client.post(
        "/api/v1/master-data/document-statuses",
        headers=headers,
        json={
            "code": "DRAFT",
            "name": "Draft",
            "displayOrder": 10,
            "isInitial": True,
        },
    )
    assert draft.status_code == 201, draft.text
    second_initial = await api_client.post(
        "/api/v1/master-data/document-statuses",
        headers=headers,
        json={
            "code": "NEW",
            "name": "New",
            "displayOrder": 20,
            "isInitial": True,
        },
    )
    assert second_initial.status_code == 409, second_initial.text
    negative_order = await api_client.post(
        "/api/v1/master-data/document-statuses",
        headers=headers,
        json={"code": "BAD", "name": "Bad", "displayOrder": -1},
    )
    assert negative_order.status_code == 422


@pytest.mark.asyncio
async def test_validation_rule_business_validation_and_defaults(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _admin_headers(create_user, token_service)
    base = {
        "code": "RULE-ONE",
        "name": "Rule One",
        "requiredIndonesian": True,
        "requiredEnglish": False,
        "requiredChinese": False,
        "minimumIndonesianCoverage": 95,
        "minimumEnglishCoverage": 0,
        "minimumChineseCoverage": 0,
        "validateLanguageOrder": True,
        "languageOrder": ["id"],
        "validateSections": True,
        "requiredSections": ["TITLE", "PURPOSE"],
        "minimumComplianceScore": 90,
        "partialComplianceScore": 70,
        "isDefault": True,
    }
    created = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json=base,
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["languageOrder"] == ["id"]
    assert data["requiredSections"] == ["TITLE", "PURPOSE"]

    all_false = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            **base,
            "code": "NONE",
            "isDefault": False,
            "requiredIndonesian": False,
        },
    )
    assert all_false.status_code == 422

    score_invalid = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            **base,
            "code": "SCORE",
            "isDefault": False,
            "partialComplianceScore": 95,
            "minimumComplianceScore": 80,
        },
    )
    assert score_invalid.status_code == 422

    second_default = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={**base, "code": "RULE-TWO", "name": "Rule Two"},
    )
    assert second_default.status_code == 409, second_default.text

    non_default = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            **base,
            "code": "RULE-THREE",
            "name": "Rule Three",
            "isDefault": False,
        },
    )
    assert non_default.status_code == 201, non_default.text
    default_bypass = await api_client.put(
        "/api/v1/master-data/validation-rules/"
        f"{non_default.json()['data']['id']}",
        headers=headers,
        json={"isDefault": True},
    )
    assert default_bypass.status_code == 400
    assert default_bypass.json()["errors"][0]["field"] == "isDefault"
    dedicated = await api_client.patch(
        "/api/v1/master-data/validation-rules/"
        f"{non_default.json()['data']['id']}/set-default",
        headers=headers,
    )
    assert dedicated.status_code == 200, dedicated.text
    assert dedicated.json()["data"]["isDefault"] is True

    inactive_default = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            **base,
            "code": "INACTIVE",
            "isDefault": True,
            "isActive": False,
        },
    )
    assert inactive_default.status_code == 422


@pytest.mark.asyncio
async def test_overview_uses_database_counts(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _admin_headers(create_user, token_service)
    await api_client.post(
        "/api/v1/master-data/departments",
        headers=headers,
        json={"code": "ONE", "name": "One"},
    )
    two = await api_client.post(
        "/api/v1/master-data/departments",
        headers=headers,
        json={"code": "TWO", "name": "Two"},
    )
    await api_client.patch(
        f"/api/v1/master-data/departments/{two.json()['data']['id']}/deactivate",
        headers=headers,
    )
    response = await api_client.get(
        "/api/v1/master-data/overview",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["departments"] == {
        "total": 2,
        "active": 1,
        "inactive": 1,
    }

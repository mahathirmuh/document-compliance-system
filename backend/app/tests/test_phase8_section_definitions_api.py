"""Focused Phase 8 section master-data API tests."""

from collections.abc import AsyncIterator, Callable
from io import BytesIO
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies.auth import get_token_service
from app.api.v1.endpoints.section_definitions import router
from app.core.authorization import UserRole
from app.core.exception_handlers import register_exception_handlers
from app.database.session import get_db_session
from app.services.auth.token_service import TokenService
from app.services.master_data.section_alias_import_export_service import (
    ALIAS_HEADERS,
    DEFINITION_HEADERS,
)

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


@pytest_asyncio.fixture
async def section_api_client(
    session_factory: TestSessionFactory,
    token_service: TokenService,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(router, prefix="/api/v1/master-data")
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_token_service] = lambda: token_service
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield client


async def _headers(
    create_user: UserFactory,
    token_service: TokenService,
    *,
    email: str,
    role: UserRole = UserRole.SUPER_ADMIN,
    is_superuser: bool = True,
) -> dict[str, str]:
    user = await create_user(
        email=email,
        role=role,
        is_superuser=is_superuser,
    )
    return {
        "Authorization": f"Bearer {token_service.create_access_token(user)}"
    }


def _workbook(
    *,
    display_name: str = "Purpose",
    priority: int = 100,
) -> bytes:
    workbook = Workbook()
    definitions = workbook.active
    definitions.title = "Section Definitions"
    definitions.append(DEFINITION_HEADERS)
    definitions.append(
        (
            "PURPOSE",
            display_name,
            "Document purpose.",
            10,
            True,
            False,
            True,
        )
    )
    aliases = workbook.create_sheet("Section Aliases")
    aliases.append(ALIAS_HEADERS)
    aliases.append(
        (
            "PURPOSE",
            "id",
            "Tujuan",
            "EXACT",
            priority,
            False,
            True,
        )
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.mark.asyncio
async def test_section_catalog_crud_filters_and_frontend_match_contract(
    section_api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _headers(
        create_user,
        token_service,
        email="section-admin@example.com",
    )
    profile_response = await section_api_client.post(
        "/api/v1/master-data/section-alias-profiles",
        headers=headers,
        json={
            "code": "corporate",
            "name": "Corporate",
            "isDefault": True,
        },
    )
    assert profile_response.status_code == 201, profile_response.text
    profile = profile_response.json()["data"]
    assert profile["code"] == "CORPORATE"
    assert profile["isDefault"] is True

    definition_response = await section_api_client.post(
        "/api/v1/master-data/section-definitions",
        headers=headers,
        json={
            "profileId": profile["id"],
            "canonicalCode": "responsibility",
            "displayName": "Responsibility",
            "displayOrder": 20,
            "isRequiredDefault": True,
        },
    )
    assert definition_response.status_code == 201, definition_response.text
    definition = definition_response.json()["data"]

    alias_response = await section_api_client.post(
        "/api/v1/master-data/section-aliases",
        headers=headers,
        json={
            "sectionDefinitionId": definition["id"],
            "languageCode": "id",
            "aliasText": "Tanggung Jawab",
            "matchType": "EXACT",
            "priority": 100,
            "isRegex": False,
        },
    )
    assert alias_response.status_code == 201, alias_response.text
    alias = alias_response.json()["data"]
    assert alias["canonicalCode"] == "RESPONSIBILITY"

    listed = await section_api_client.get(
        "/api/v1/master-data/section-aliases",
        headers=headers,
        params={
            "profileId": profile["id"],
            "languageCode": "id",
            "search": "tanggung",
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["totalItems"] == 1

    matched = await section_api_client.post(
        "/api/v1/master-data/section-definitions/test-match",
        headers=headers,
        json={
            "headingText": "2. TANGGUNG JAWAB",
            "profileId": profile["id"],
        },
    )
    assert matched.status_code == 200, matched.text
    match = matched.json()["data"]
    assert match["matched"] is True
    assert match["canonicalCode"] == "RESPONSIBILITY"
    assert match["normalisedHeading"] == "tanggung jawab"
    assert "normalizedHeading" not in match

    deactivated = await section_api_client.patch(
        f"/api/v1/master-data/section-aliases/{alias['id']}/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["isActive"] is False
    activated = await section_api_client.patch(
        f"/api/v1/master-data/section-aliases/{alias['id']}/activate",
        headers=headers,
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["data"]["isActive"] is True


@pytest.mark.asyncio
async def test_section_catalog_permissions_are_enforced_at_api_boundary(
    section_api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    reader_headers = await _headers(
        create_user,
        token_service,
        email="section-reader@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        is_superuser=False,
    )
    listed = await section_api_client.get(
        "/api/v1/master-data/section-alias-profiles",
        headers=reader_headers,
    )
    assert listed.status_code == 200, listed.text
    forbidden = await section_api_client.post(
        "/api/v1/master-data/section-alias-profiles",
        headers=reader_headers,
        json={"code": "NOPE", "name": "Not Allowed"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["success"] is False

    viewer_headers = await _headers(
        create_user,
        token_service,
        email="plain-viewer@example.com",
        role=UserRole.VIEWER,
        is_superuser=False,
    )
    no_master_data_permission = await section_api_client.get(
        "/api/v1/master-data/section-alias-profiles",
        headers=viewer_headers,
    )
    assert no_master_data_permission.status_code == 403


@pytest.mark.asyncio
async def test_section_import_token_modes_binding_and_default_export(
    section_api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _headers(
        create_user,
        token_service,
        email="section-importer@example.com",
    )
    profile_response = await section_api_client.post(
        "/api/v1/master-data/section-alias-profiles",
        headers=headers,
        json={
            "code": "IMPORT",
            "name": "Import Profile",
            "isDefault": True,
        },
    )
    assert profile_response.status_code == 201, profile_response.text

    async def preview(content: bytes) -> dict[str, Any]:
        response = await section_api_client.post(
            "/api/v1/master-data/section-definitions/import/preview",
            headers=headers,
            files={
                "file": (
                    "section-aliases.xlsx",
                    content,
                    (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    first_preview = await preview(_workbook())
    assert first_preview["definitions"] == 1
    assert first_preview["aliases"] == 1
    assert first_preview["validRows"] == 2
    assert first_preview["invalidRows"] == 0
    assert first_preview["duplicateRows"] == 0
    assert first_preview["warnings"][0].startswith("Default profile IMPORT")

    other_headers = await _headers(
        create_user,
        token_service,
        email="other-section-admin@example.com",
    )
    bound_to_user = await section_api_client.post(
        "/api/v1/master-data/section-definitions/import/confirm",
        headers=other_headers,
        json={
            "importToken": first_preview["importToken"],
            "mode": "CREATE_ONLY",
        },
    )
    assert bound_to_user.status_code == 400
    assert bound_to_user.json()["errors"][0]["field"] == "importToken"

    created = await section_api_client.post(
        "/api/v1/master-data/section-definitions/import/confirm",
        headers=headers,
        json={
            "importToken": first_preview["importToken"],
            "mode": "CREATE_ONLY",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"] == {
        "totalRows": 2,
        "created": 2,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }

    duplicate_preview = await preview(_workbook())
    assert duplicate_preview["duplicateRows"] == 2
    skipped = await section_api_client.post(
        "/api/v1/master-data/section-definitions/import/confirm",
        headers=headers,
        json={
            "importToken": duplicate_preview["importToken"],
            "mode": "CREATE_ONLY",
        },
    )
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["data"]["skipped"] == 2
    assert skipped.json()["data"]["updated"] == 0

    update_preview = await preview(
        _workbook(display_name="Purpose and Objective", priority=250)
    )
    updated = await section_api_client.post(
        "/api/v1/master-data/section-definitions/import/confirm",
        headers=headers,
        json={
            "importToken": update_preview["importToken"],
            "mode": "UPSERT",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["updated"] == 2
    assert updated.json()["data"]["skipped"] == 0

    definitions = await section_api_client.get(
        "/api/v1/master-data/section-definitions",
        headers=headers,
        params={"search": "objective"},
    )
    assert definitions.status_code == 200, definitions.text
    assert definitions.json()["data"]["items"][0]["displayName"] == (
        "Purpose and Objective"
    )

    exported = await section_api_client.get(
        "/api/v1/master-data/section-definitions/export",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert exported.content.startswith(b"PK")
    assert exported.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "section_aliases_IMPORT_" in exported.headers[
        "content-disposition"
    ]
    assert exported.headers["cache-control"] == "private, no-store"

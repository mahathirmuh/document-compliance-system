"""Phase 4 Document Register and revision API integration tests."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import AuditAction, UserRole
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.section import Section
from app.models.validation_rule import ValidationRule
from app.services.auth.token_service import TokenService

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


async def _seed_master(
    session_factory: TestSessionFactory,
) -> dict[str, Any]:
    async with session_factory() as session:
        department = Department(code="HRM", name="Human Resource")
        other_department = Department(code="ICT", name="Technology")
        session.add_all((department, other_department))
        await session.flush()
        section = Section(
            department_id=department.id,
            code="IER",
            name="Industrial Relations",
        )
        other_section = Section(
            department_id=other_department.id,
            code="OPS",
            name="Operations",
        )
        document_type = DocumentType(
            code="SOP",
            name="Standard Operating Procedure",
            requires_section=True,
        )
        no_section_type = DocumentType(
            code="POL",
            name="Policy",
            requires_section=False,
        )
        initial = DocumentStatus(
            code="DRAFT",
            name="Draft",
            is_initial=True,
            display_order=1,
        )
        effective = DocumentStatus(
            code="EFFECTIVE",
            name="Effective",
            is_final=True,
            display_order=2,
        )
        superseded = DocumentStatus(
            code="SUPERSEDED",
            name="Superseded",
            is_obsolete=True,
            display_order=3,
        )
        session.add_all(
            (
                section,
                other_section,
                document_type,
                no_section_type,
                initial,
                effective,
                superseded,
            )
        )
        await session.flush()
        rule = ValidationRule(
            code="DEFAULT",
            name="Default Rule",
            is_default=True,
            is_active=True,
        )
        typed_rule = ValidationRule(
            code="SOP-RULE",
            name="SOP Rule",
            document_type_id=document_type.id,
            is_default=True,
            is_active=True,
        )
        session.add_all((rule, typed_rule))
        await session.flush()
        document_type.default_validation_rule_id = typed_rule.id
        await session.commit()
        return {
            "department": department,
            "other_department": other_department,
            "section": section,
            "other_section": other_section,
            "document_type": document_type,
            "no_section_type": no_section_type,
            "initial": initial,
            "effective": effective,
            "superseded": superseded,
            "rule": rule,
            "typed_rule": typed_rule,
        }


async def _headers(
    create_user: UserFactory,
    token_service: TokenService,
    *,
    role: UserRole = UserRole.SUPER_ADMIN,
    department_id: Any | None = None,
    suffix: str = "admin",
) -> dict[str, str]:
    user = await create_user(
        email=f"documents-{suffix}@example.com",
        role=role,
        department_id=department_id,
        is_superuser=role is UserRole.SUPER_ADMIN,
    )
    token = token_service.create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def _create_payload(master: dict[str, Any]) -> dict[str, Any]:
    return {
        "companyCode": "mti",
        "departmentId": str(master["department"].id),
        "sectionId": str(master["section"].id),
        "documentTypeId": str(master["document_type"].id),
        "documentNumber": "001",
        "title": "Worker Grievance Procedure",
        "description": "Trilingual controlled procedure.",
        "initialRevision": {
            "revisionCode": "0",
            "setAsCurrent": False,
        },
    }


@pytest.mark.asyncio
async def test_create_initial_revision_defaults_duplicate_list_and_audit(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(create_user, token_service)
    payload = _create_payload(master)

    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["baseDocumentCode"] == "MTI-HRM-IER-SOP-001"
    assert data["departmentId"] == str(master["department"].id)
    assert data["ownerDepartmentId"] == str(master["department"].id)
    assert data["currentRevision"]["revisionCode"] == "Rev.000"
    assert data["currentRevision"]["isCurrent"] is True
    assert data["currentRevision"]["status"]["code"] == "DRAFT"
    assert data["currentRevision"]["validationRule"]["code"] == "SOP-RULE"
    assert len(data["revisions"]) == 1

    duplicate = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=payload,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["errors"][0]["field"] == "documentNumber"

    listed = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={
            "search": "grievance",
            "departmentId": str(master["department"].id),
            "documentStatusId": str(master["initial"].id),
            "page": 1,
            "pageSize": 10,
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["totalItems"] == 1
    assert listed.json()["data"]["items"][0]["id"] == data["id"]

    async with session_factory() as session:
        actions = set((await session.scalars(select(AuditLog.action))).all())
    assert AuditAction.CREATE_DOCUMENT in actions
    assert AuditAction.CREATE_DOCUMENT_REVISION in actions


@pytest.mark.asyncio
async def test_identity_validation_and_create_transaction_rollback(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(create_user, token_service)
    payload = _create_payload(master)

    missing_section = dict(payload)
    missing_section["sectionId"] = None
    response = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=missing_section,
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "sectionId"

    mismatch = dict(payload)
    mismatch["sectionId"] = str(master["other_section"].id)
    response = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=mismatch,
    )
    assert response.status_code == 400
    assert "does not belong" in response.text

    invalid_revision = dict(payload)
    invalid_revision["initialRevision"] = {"revisionCode": "bad/revision"}
    response = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=invalid_revision,
    )
    assert response.status_code == 422

    async with session_factory() as session:
        assert await session.scalar(select(Document)) is None

    async with session_factory() as session:
        department = await session.get(
            Department,
            master["department"].id,
        )
        assert department is not None
        department.is_active = False
        await session.commit()
    response = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 400
    assert "must be active" in response.text


@pytest.mark.asyncio
async def test_list_all_filters_sorting_and_pagination(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="list-filters",
    )
    first_payload = _create_payload(master)
    first_payload["documentNumber"] = "100"
    first_payload["initialRevision"] = {
        "revisionCode": "5",
        "effectiveDate": "2026-08-01",
        "sharepointUrl": "https://example.sharepoint.com/100",
    }
    first = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=first_payload,
    )
    assert first.status_code == 201, first.text
    second_payload = {
        "companyCode": "ALT",
        "departmentId": str(master["department"].id),
        "sectionId": None,
        "documentTypeId": str(master["no_section_type"].id),
        "documentNumber": "200",
        "title": "Policy without section",
        "initialRevision": {"revisionCode": "0"},
    }
    second = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=second_payload,
    )
    assert second.status_code == 201, second.text

    expected_first_filters = {
        "sectionId": str(master["section"].id),
        "documentTypeId": str(master["document_type"].id),
        "revisionCode": "Rev.005",
        "companyCode": "MTI",
        "hasSharePointUrl": True,
        "effectiveFrom": "2026-08-01",
        "effectiveTo": "2026-08-01",
    }
    for name, value in expected_first_filters.items():
        response = await api_client.get(
            "/api/v1/documents",
            headers=headers,
            params={name: value},
        )
        assert response.status_code == 200, (name, response.text)
        assert response.json()["data"]["totalItems"] == 1, name
        assert (
            response.json()["data"]["items"][0]["id"]
            == first.json()["data"]["id"]
        )

    application_date = datetime.now(
        ZoneInfo("Asia/Makassar")
    ).date().isoformat()
    created_range = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={
            "createdFrom": application_date,
            "createdTo": application_date,
        },
    )
    assert created_range.status_code == 200
    assert created_range.json()["data"]["totalItems"] == 2

    without_url = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={"hasSharePointUrl": False},
    )
    assert without_url.status_code == 200
    assert without_url.json()["data"]["items"][0]["id"] == second.json()[
        "data"
    ]["id"]

    first_page = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={
            "sortBy": "baseDocumentCode",
            "sortOrder": "asc",
            "page": 1,
            "pageSize": 1,
        },
    )
    second_page = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={
            "sortBy": "baseDocumentCode",
            "sortOrder": "asc",
            "page": 2,
            "pageSize": 1,
        },
    )
    assert first_page.json()["data"]["totalItems"] == 2
    assert first_page.json()["data"]["totalPages"] == 2
    assert first_page.json()["data"]["items"][0]["baseDocumentCode"].startswith(
        "ALT-"
    )
    assert second_page.json()["data"]["items"][0]["baseDocumentCode"].startswith(
        "MTI-"
    )


@pytest.mark.asyncio
async def test_existing_inactive_master_values_remain_editable_when_unchanged(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="inactive-existing",
    )
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=_create_payload(master),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    async with session_factory() as session:
        for model, entity in (
            (Department, master["department"]),
            (Department, master["other_department"]),
            (Section, master["section"]),
            (DocumentType, master["document_type"]),
        ):
            stored = await session.get(model, entity.id)
            assert stored is not None
            stored.is_active = False
        await session.commit()

    updated = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=headers,
        json={
            "companyCode": "MTI",
            "departmentId": str(master["department"].id),
            "sectionId": str(master["section"].id),
            "documentTypeId": str(master["document_type"].id),
            "documentNumber": "001",
            "title": "Metadata update on legacy master data",
            "ownerDepartmentId": str(master["department"].id),
        },
    )
    assert updated.status_code == 200, updated.text
    assert (
        updated.json()["data"]["title"]
        == "Metadata update on legacy master data"
    )
    assert updated.json()["data"]["ownerDepartmentId"] == str(
        master["department"].id
    )

    changed_owner = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=headers,
        json={
            "ownerDepartmentId": str(master["other_department"].id),
        },
    )
    assert changed_owner.status_code == 400
    assert "must be active" in changed_owner.text


@pytest.mark.asyncio
async def test_department_scope_and_rbac_are_backend_enforced(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    admin = await _headers(
        create_user,
        token_service,
        suffix="scope-admin",
    )
    created = await api_client.post(
        "/api/v1/documents",
        headers=admin,
        json=_create_payload(master),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]

    other_user = await _headers(
        create_user,
        token_service,
        role=UserRole.DEPARTMENT_USER,
        department_id=master["other_department"].id,
        suffix="other-department",
    )
    listed = await api_client.get("/api/v1/documents", headers=other_user)
    assert listed.status_code == 200
    assert listed.json()["data"]["totalItems"] == 0
    detail = await api_client.get(
        f"/api/v1/documents/{document_id}",
        headers=other_user,
    )
    assert detail.status_code == 403
    forbidden_create = await api_client.post(
        "/api/v1/documents",
        headers=other_user,
        json=_create_payload(master),
    )
    assert forbidden_create.status_code == 403

    department_user = await _headers(
        create_user,
        token_service,
        role=UserRole.DEPARTMENT_USER,
        department_id=master["department"].id,
        suffix="own-department",
    )
    form_options = await api_client.get(
        "/api/v1/documents/form-options",
        headers=department_user,
    )
    assert form_options.status_code == 200, form_options.text
    option_data = form_options.json()["data"]
    assert option_data["defaultCompanyCode"] == "MTI"
    assert [item["code"] for item in option_data["departments"]] == ["HRM"]
    assert [item["code"] for item in option_data["sections"]] == ["IER"]
    sop_option = next(
        item
        for item in option_data["documentTypes"]
        if item["code"] == "SOP"
    )
    assert sop_option["requiresSection"] is True
    assert sop_option["defaultValidationRuleId"] == str(
        master["typed_rule"].id
    )
    assert any(
        item["isInitial"]
        for item in option_data["documentStatuses"]
    )
    assert any(
        item["documentTypeId"] == str(master["document_type"].id)
        and item["isDefault"]
        for item in option_data["validationRules"]
    )
    updated = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=department_user,
        json={"title": "Department-owned update"},
    )
    assert updated.status_code == 200, updated.text
    moved = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=department_user,
        json={
            "departmentId": str(master["other_department"].id),
            "sectionId": str(master["other_section"].id),
            "changeReason": "Attempted move",
        },
    )
    assert moved.status_code == 403

    viewer = await _headers(
        create_user,
        token_service,
        role=UserRole.VIEWER,
        department_id=master["department"].id,
        suffix="viewer",
    )
    denied = await api_client.post(
        "/api/v1/documents",
        headers=viewer,
        json=_create_payload(master),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_parse_code_resolves_master_data_and_rejects_ambiguity(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    async with session_factory() as session:
        hyphen_type = DocumentType(
            code="WORK-INSTRUCTION",
            name="Work Instruction",
            requires_section=True,
        )
        session.add(hyphen_type)
        await session.commit()
    headers = await _headers(
        create_user,
        token_service,
        suffix="parser",
    )
    cases = (
        (
            "MTI-HRM-IER-SOP-001_Rev.003.pdf",
            "pdf",
            "IER",
            "001",
        ),
        (
            "MTI-HRM-IER-SOP-001_Rev.003.xlsx",
            "xlsx",
            "IER",
            "001",
        ),
        (
            "MTI-HRM-POL-2026-001_Rev.003.docx",
            "docx",
            None,
            "2026-001",
        ),
    )
    for value, extension, section_code, number in cases:
        response = await api_client.post(
            "/api/v1/documents/parse-code",
            headers=headers,
            json={"value": value},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["fileExtension"] == extension
        assert (
            data["section"]["code"] if data["section"] is not None else None
        ) == section_code
        assert data["documentNumber"] == number
        assert data["revisionCode"] == "Rev.003"

    hyphenated = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={
            "value": (
                "MTI-HRM-IER-WORK-INSTRUCTION-2026-001_Rev.A.pdf"
            )
        },
    )
    assert hyphenated.status_code == 200, hyphenated.text
    assert hyphenated.json()["data"]["documentType"]["code"] == (
        "WORK-INSTRUCTION"
    )
    assert hyphenated.json()["data"]["documentNumber"] == "2026-001"

    create_payload = _create_payload(master)
    create_payload["documentTypeId"] = str(hyphen_type.id)
    create_payload["documentNumber"] = "WI-001"
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=create_payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["baseDocumentCode"] == (
        "MTI-HRM-IER-WORK-INSTRUCTION-WI-001"
    )

    async with session_factory() as session:
        session.add(
            DocumentType(
                code="WORK",
                name="Ambiguous Work Type",
                requires_section=True,
            )
        )
        await session.commit()
    ambiguous = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={
            "value": (
                "MTI-HRM-IER-WORK-INSTRUCTION-2026-001_Rev.A.pdf"
            )
        },
    )
    assert ambiguous.status_code == 400
    assert "ambiguous" in ambiguous.text

    unknown_department = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={"value": "MTI-XXX-IER-SOP-001_Rev.001.pdf"},
    )
    assert unknown_department.status_code == 400
    assert "Department code" in unknown_department.text

    unknown_type = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={"value": "MTI-HRM-IER-XXX-001_Rev.001.pdf"},
    )
    assert unknown_type.status_code == 400
    assert "Document Type code" in unknown_type.text

    mismatch = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={"value": "MTI-ICT-IER-SOP-001_Rev.001.pdf"},
    )
    assert mismatch.status_code == 400
    assert "does not belong" in mismatch.text

    unsupported = await api_client.post(
        "/api/v1/documents/parse-code",
        headers=headers,
        json={"value": "MTI-HRM-IER-SOP-001_Rev.003.txt"},
    )
    assert unsupported.status_code == 400
    assert "not supported" in unsupported.text


@pytest.mark.asyncio
async def test_code_change_archive_restore_and_bulk_actions(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="lifecycle",
    )
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=_create_payload(master),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]

    no_reason = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=headers,
        json={"documentNumber": "002"},
    )
    assert no_reason.status_code == 400
    changed = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=headers,
        json={
            "documentNumber": "002",
            "changeReason": "Controlled correction",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["baseDocumentCode"].endswith("-002")
    base_document_code = changed.json()["data"]["baseDocumentCode"]
    revision_id = changed.json()["data"]["currentRevision"]["id"]
    assert (
        changed.json()["data"]["currentRevision"]["fullDocumentCode"]
        == "MTI-HRM-IER-SOP-002_Rev.000"
    )

    blank_reason = await api_client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank_reason.status_code == 422
    archived = await api_client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=headers,
        json={"reason": "No longer in use."},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["data"]["isArchived"] is True
    default_list = await api_client.get(
        "/api/v1/documents",
        headers=headers,
    )
    assert default_list.json()["data"]["totalItems"] == 0
    archive_list = await api_client.get(
        "/api/v1/documents",
        headers=headers,
        params={"isArchived": True},
    )
    assert archive_list.json()["data"]["totalItems"] == 1
    read_only = await api_client.put(
        f"/api/v1/documents/{document_id}",
        headers=headers,
        json={"title": "Should fail"},
    )
    assert read_only.status_code == 400
    restored = await api_client.post(
        f"/api/v1/documents/{document_id}/restore",
        headers=headers,
        json={},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["isArchived"] is False

    bulk_archive = await api_client.post(
        "/api/v1/documents/bulk/archive",
        headers=headers,
        json={
            "documentIds": [document_id],
            "reason": "Bulk cleanup",
        },
    )
    assert bulk_archive.status_code == 200, bulk_archive.text
    assert bulk_archive.json()["data"]["succeeded"] == 1
    bulk_restore = await api_client.post(
        "/api/v1/documents/bulk/restore",
        headers=headers,
        json={"documentIds": [document_id]},
    )
    assert bulk_restore.status_code == 200, bulk_restore.text
    assert bulk_restore.json()["data"]["succeeded"] == 1
    async with session_factory() as session:
        archive_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.BULK_ARCHIVE_DOCUMENTS
            )
        )
        restore_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.BULK_RESTORE_DOCUMENTS
            )
        )
        assert archive_audit is not None
        assert archive_audit.new_values_json is not None
        assert archive_audit.new_values_json["changeCount"] == 1
        archive_change = archive_audit.new_values_json["changes"][0]
        assert archive_change["documentId"] == document_id
        assert archive_change["baseDocumentCode"] == base_document_code
        assert archive_change["revisionId"] == revision_id
        assert archive_change["oldValues"]["isArchived"] is False
        assert archive_change["newValues"]["isArchived"] is True
        assert restore_audit is not None
        assert restore_audit.new_values_json is not None
        assert restore_audit.new_values_json["changeCount"] == 1
        restore_change = restore_audit.new_values_json["changes"][0]
        assert restore_change["documentId"] == document_id
        assert restore_change["baseDocumentCode"] == base_document_code
        assert restore_change["revisionId"] == revision_id
        assert restore_change["oldValues"]["isArchived"] is True
        assert restore_change["newValues"]["isArchived"] is False


@pytest.mark.asyncio
async def test_first_standalone_revision_is_always_current(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="first-standalone-revision",
    )
    payload = _create_payload(master)
    payload.pop("initialRevision")
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    assert created.json()["data"]["currentRevision"] is None

    revision = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions",
        headers=headers,
        json={"revisionCode": "0", "setAsCurrent": False},
    )
    assert revision.status_code == 201, revision.text
    assert revision.json()["data"]["isCurrent"] is True

    detail = await api_client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["currentRevision"]["id"] == (
        revision.json()["data"]["id"]
    )


@pytest.mark.asyncio
async def test_revision_update_preserves_unchanged_inactive_references(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="inactive-revision-references",
    )
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=_create_payload(master),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    revision_id = created.json()["data"]["currentRevision"]["id"]

    async with session_factory() as session:
        for entity_type, entity_id in (
            (DocumentStatus, master["initial"].id),
            (ValidationRule, master["typed_rule"].id),
            (DocumentStatus, master["effective"].id),
            (ValidationRule, master["rule"].id),
        ):
            entity = await session.get(entity_type, entity_id)
            assert entity is not None
            entity.is_active = False
        await session.commit()

    unchanged = await api_client.put(
        f"/api/v1/documents/{document_id}/revisions/{revision_id}",
        headers=headers,
        json={
            "documentStatusId": str(master["initial"].id),
            "validationRuleId": str(master["typed_rule"].id),
            "remarks": "Historical references retained",
        },
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["data"]["documentStatusId"] == str(
        master["initial"].id
    )
    assert unchanged.json()["data"]["validationRuleId"] == str(
        master["typed_rule"].id
    )
    assert unchanged.json()["data"]["remarks"] == (
        "Historical references retained"
    )

    cleared_rule = await api_client.put(
        f"/api/v1/documents/{document_id}/revisions/{revision_id}",
        headers=headers,
        json={"validationRuleId": None},
    )
    assert cleared_rule.status_code == 200, cleared_rule.text
    assert cleared_rule.json()["data"]["validationRuleId"] is None
    assert cleared_rule.json()["data"]["validationRule"] is None

    changed_status = await api_client.put(
        f"/api/v1/documents/{document_id}/revisions/{revision_id}",
        headers=headers,
        json={"documentStatusId": str(master["effective"].id)},
    )
    assert changed_status.status_code == 400
    assert "must be active" in changed_status.text

    changed_rule = await api_client.put(
        f"/api/v1/documents/{document_id}/revisions/{revision_id}",
        headers=headers,
        json={"validationRuleId": str(master["rule"].id)},
    )
    assert changed_rule.status_code == 400
    assert "must be active" in changed_rule.text


@pytest.mark.asyncio
async def test_revision_management_current_supersede_and_dates(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="revisions",
    )
    created = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=_create_payload(master),
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    base_document_code = created.json()["data"]["baseDocumentCode"]
    first_id = created.json()["data"]["currentRevision"]["id"]

    invalid_date = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions",
        headers=headers,
        json={
            "revisionCode": "1",
            "effectiveDate": "2026-08-01",
            "expiryDate": "2026-07-01",
        },
    )
    assert invalid_date.status_code == 422

    second = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions",
        headers=headers,
        json={
            "revisionCode": "1",
            "documentStatusId": str(master["effective"].id),
            "issueDate": "2026-07-25",
            "effectiveDate": "2026-08-01",
            "setAsCurrent": True,
        },
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["data"]["id"]
    assert second.json()["data"]["revisionCode"] == "Rev.001"
    duplicate = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions",
        headers=headers,
        json={"revisionCode": "Rev001"},
    )
    assert duplicate.status_code == 409

    revision_change_without_reason = await api_client.put(
        (
            f"/api/v1/documents/{document_id}/revisions/"
            f"{second_id}"
        ),
        headers=headers,
        json={"revisionCode": "2"},
    )
    assert revision_change_without_reason.status_code == 400
    revision_changed = await api_client.put(
        (
            f"/api/v1/documents/{document_id}/revisions/"
            f"{second_id}"
        ),
        headers=headers,
        json={
            "revisionCode": "2",
            "changeReason": "Correction of revision identifier",
        },
    )
    assert revision_changed.status_code == 200, revision_changed.text
    assert revision_changed.json()["data"]["revisionCode"] == "Rev.002"

    revisions = await api_client.get(
        f"/api/v1/documents/{document_id}/revisions",
        headers=headers,
    )
    assert revisions.status_code == 200
    assert sum(item["isCurrent"] for item in revisions.json()["data"]) == 1

    set_first = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions/{first_id}/set-current",
        headers=headers,
        json={"reason": "Temporary rollback"},
    )
    assert set_first.status_code == 200, set_first.text
    assert set_first.json()["data"]["isCurrent"] is True

    self_supersede = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions/{first_id}/supersede",
        headers=headers,
        json={
            "supersededByRevisionId": first_id,
            "reason": "Invalid",
        },
    )
    assert self_supersede.status_code == 400
    superseded = await api_client.post(
        f"/api/v1/documents/{document_id}/revisions/{first_id}/supersede",
        headers=headers,
        json={
            "supersededByRevisionId": second_id,
            "reason": "Replaced by Rev.001",
        },
    )
    assert superseded.status_code == 200, superseded.text
    assert superseded.json()["data"]["isSuperseded"] is True
    detail = await api_client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )
    assert detail.json()["data"]["currentRevision"]["id"] == second_id

    bulk_status = await api_client.post(
        "/api/v1/documents/bulk/update-status",
        headers=headers,
        json={
            "documentIds": [document_id],
            "documentStatusId": str(master["initial"].id),
            "reason": "Status alignment",
        },
    )
    assert bulk_status.status_code == 200, bulk_status.text
    assert bulk_status.json()["data"]["succeeded"] == 1
    async with session_factory() as session:
        status_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.BULK_UPDATE_DOCUMENT_STATUS
            )
        )
        assert status_audit is not None
        assert status_audit.new_values_json is not None
        assert status_audit.new_values_json["changeCount"] == 1
        status_change = status_audit.new_values_json["changes"][0]
        assert status_change["documentId"] == document_id
        assert status_change["baseDocumentCode"] == base_document_code
        assert status_change["revisionId"] == second_id
        assert status_change["oldValues"] == {
            "documentStatusId": str(master["effective"].id),
            "documentStatusCode": "EFFECTIVE",
        }
        assert status_change["newValues"] == {
            "documentStatusId": str(master["initial"].id),
            "documentStatusCode": "DRAFT",
        }

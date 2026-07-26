"""Phase 8 section-profile, canonical-section, and alias endpoints."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

import jwt
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_request_metadata,
    require_permissions,
)
from app.core.authorization import Permission
from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.database.session import get_db_session
from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
)
from app.models.section_alias_profile import SectionAliasProfile
from app.models.user import User
from app.schemas.common import ApiResponse, ErrorDetail
from app.schemas.section_detection import (
    SectionAliasCreate,
    SectionAliasImportConfirmRequest,
    SectionAliasImportConfirmResponse,
    SectionAliasImportError,
    SectionAliasImportPreview,
    SectionAliasImportPreviewRow,
    SectionAliasImportTokenResponse,
    SectionAliasListResponse,
    SectionAliasProfileCreate,
    SectionAliasProfileListResponse,
    SectionAliasProfileResponse,
    SectionAliasProfileUpdate,
    SectionAliasResponse,
    SectionAliasUpdate,
    SectionDefinitionCreate,
    SectionDefinitionListResponse,
    SectionDefinitionResponse,
    SectionDefinitionUpdate,
    SectionMatchTestRequest,
    SectionMatchTestResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import business_error, not_found
from app.services.master_data.section_alias_import_export_service import (
    SectionAliasImportExportService,
)
from app.services.master_data.section_alias_service import (
    SectionAliasService,
    normalise_alias,
)
from app.services.master_data.section_definition_service import (
    SectionAliasProfileService,
    SectionDefinitionService,
)

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Metadata = Annotated[RequestMetadata, Depends(get_request_metadata)]
MasterDataViewer = Annotated[
    User,
    Depends(require_permissions(Permission.MASTER_DATA_VIEW)),
]
SectionConfigurer = Annotated[
    User,
    Depends(require_permissions(Permission.COMPLIANCE_CONFIGURE_RULES)),
]

SortOrder = Literal["asc", "desc"]
SheetName = Literal["Section Definitions", "Section Aliases"]
XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_IMPORT_TOKEN_TYPE = "section_alias_import"
_IMPORT_TOKEN_TTL = timedelta(minutes=15)
_IMPORT_TOKEN_MAX_LENGTH = 8_000_000
_SHEETS: tuple[SheetName, SheetName] = (
    "Section Definitions",
    "Section Aliases",
)


def _profile_service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> SectionAliasProfileService:
    return SectionAliasProfileService(session, user, metadata)


def _definition_service(
    session: AsyncSession,
    user: User,
    metadata: RequestMetadata,
) -> SectionDefinitionService:
    return SectionDefinitionService(session, user, metadata)


def _alias_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> SectionAliasService:
    return SectionAliasService(session, user, metadata, settings)


def _transfer_service(
    session: AsyncSession,
    settings: Settings,
    user: User,
    metadata: RequestMetadata,
) -> SectionAliasImportExportService:
    return SectionAliasImportExportService(
        session,
        user,
        metadata,
        settings,
    )


def _secret(settings: Settings) -> str:
    value = settings.jwt_secret_key
    return (
        value.get_secret_value()
        if hasattr(value, "get_secret_value")
        else str(value)
    )


def _invalid_import_token() -> ApplicationError:
    return business_error(
        "Import token is invalid or expired. Preview the workbook again.",
        field="importToken",
    )


def _encode_import_token(
    settings: Settings,
    user: User,
    preview: SectionAliasImportPreview,
) -> str:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "type": _IMPORT_TOKEN_TYPE,
            "iat": now,
            "nbf": now,
            "exp": now + _IMPORT_TOKEN_TTL,
            "jti": str(uuid4()),
            "profileId": str(preview.profile_id),
            "preview": preview.model_dump(mode="json", by_alias=False),
        },
        _secret(settings),
        algorithm=settings.jwt_algorithm,
    )
    if len(token) > _IMPORT_TOKEN_MAX_LENGTH:
        raise business_error(
            "Import preview is too large to issue a confirmation token.",
            field="file",
        )
    return token


def _decode_import_token(
    settings: Settings,
    user: User,
    token: str,
) -> SectionAliasImportPreview:
    if len(token) > _IMPORT_TOKEN_MAX_LENGTH:
        raise _invalid_import_token()
    try:
        claims = jwt.decode(
            token,
            _secret(settings),
            algorithms=[settings.jwt_algorithm],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                    "profileId",
                    "preview",
                ],
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        if (
            claims.get("sub") != str(user.id)
            or claims.get("type") != _IMPORT_TOKEN_TYPE
        ):
            raise InvalidTokenError("Unexpected import token principal or type.")
        preview = SectionAliasImportPreview.model_validate(
            claims.get("preview")
        )
        if str(preview.profile_id) != claims.get("profileId"):
            raise InvalidTokenError("Import token profile does not match.")
        return preview
    except (
        ExpiredSignatureError,
        InvalidTokenError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise _invalid_import_token() from exc


async def _resolve_profile(
    service: SectionAliasImportExportService,
    profile_id: UUID | None,
    *,
    require_active: bool,
) -> tuple[SectionAliasProfile, bool]:
    if profile_id is None:
        used_default = True
        profile = await service.profiles.get_default()
    else:
        used_default = False
        profile = await service.profiles.get_by_id(profile_id)
    if profile is None:
        if used_default:
            raise business_error(
                "No default section alias profile is configured.",
                field="profileId",
            )
        raise not_found("Section Alias Profile")
    if require_active and not profile.is_active:
        raise business_error(
            "Section alias profile must be active.",
            field="profileId",
        )
    return profile, used_default


def _with_reference_errors(
    preview: SectionAliasImportPreview,
    profile: SectionAliasProfile,
) -> SectionAliasImportPreview:
    known_codes = {
        definition.canonical_code for definition in profile.definitions
    }
    known_codes.update(
        definition.canonical_code for definition in preview.definitions
    )
    extra_errors = [
        SectionAliasImportError(
            sheet=_SHEETS[1],
            row_number=row.row_number,
            field="canonicalCode",
            message=f"Unknown canonical section {row.canonical_code}.",
        )
        for row in preview.aliases
        if row.canonical_code not in known_codes
    ]
    if not extra_errors:
        return preview
    return preview.model_copy(
        update={
            "errors": [*preview.errors, *extra_errors],
            "valid": False,
        }
    )


def _preview_response(
    *,
    preview: SectionAliasImportPreview,
    profile: SectionAliasProfile,
    import_token: str,
    used_default: bool,
) -> SectionAliasImportTokenResponse:
    errors_by_row: dict[tuple[str, int], list[str]] = defaultdict(list)
    for error in preview.errors:
        message = (
            f"{error.field}: {error.message}"
            if error.field
            else error.message
        )
        errors_by_row[(error.sheet, error.row_number)].append(message)

    existing_definitions = {
        definition.canonical_code: definition
        for definition in profile.definitions
    }
    existing_aliases = {
        (
            definition.canonical_code,
            alias.language_code,
            alias.normalised_alias,
        )
        for definition in profile.definitions
        for alias in definition.aliases
    }
    seen_definitions: set[str] = set()
    seen_aliases: set[tuple[str, object, str]] = set()
    represented_rows: set[tuple[str, int]] = set()
    rows: list[SectionAliasImportPreviewRow] = []

    for definition in preview.definitions:
        row_key = (_SHEETS[0], definition.row_number)
        represented_rows.add(row_key)
        duplicate = (
            definition.canonical_code in existing_definitions
            or definition.canonical_code in seen_definitions
        )
        seen_definitions.add(definition.canonical_code)
        errors = errors_by_row.get(row_key, [])
        rows.append(
            SectionAliasImportPreviewRow(
                sheet_name=_SHEETS[0],
                row_number=definition.row_number,
                status=(
                    "INVALID"
                    if errors
                    else "DUPLICATE"
                    if duplicate
                    else "VALID"
                ),
                data=definition.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude={"row_number"},
                ),
                errors=errors,
            )
        )

    for alias in preview.aliases:
        row_key = (_SHEETS[1], alias.row_number)
        represented_rows.add(row_key)
        normalized = normalise_alias(alias.alias_text, alias.match_type)
        alias_key = (
            alias.canonical_code,
            alias.language_code,
            normalized,
        )
        duplicate = (
            alias_key in existing_aliases or alias_key in seen_aliases
        )
        seen_aliases.add(alias_key)
        errors = errors_by_row.get(row_key, [])
        rows.append(
            SectionAliasImportPreviewRow(
                sheet_name=_SHEETS[1],
                row_number=alias.row_number,
                status=(
                    "INVALID"
                    if errors
                    else "DUPLICATE"
                    if duplicate
                    else "VALID"
                ),
                data=alias.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude={"row_number"},
                ),
                errors=errors,
            )
        )

    for (sheet, row_number), errors in errors_by_row.items():
        if (sheet, row_number) not in represented_rows:
            rows.append(
                SectionAliasImportPreviewRow(
                    sheet_name=cast(SheetName, sheet),
                    row_number=row_number,
                    status="INVALID",
                    data={},
                    errors=errors,
                )
            )

    sheet_order = {name: index for index, name in enumerate(_SHEETS)}
    rows.sort(key=lambda row: (sheet_order[row.sheet_name], row.row_number))
    duplicate_rows = sum(row.status == "DUPLICATE" for row in rows)
    warnings: list[str] = []
    if used_default:
        warnings.append(
            f"Default profile {profile.code} was selected for this import."
        )
    if duplicate_rows:
        warnings.append(
            "Duplicate rows are skipped in CREATE_ONLY mode and updated "
            "in UPSERT mode; repeated rows within the workbook are skipped."
        )
    return SectionAliasImportTokenResponse(
        import_token=import_token,
        definitions=sum(row.sheet_name == _SHEETS[0] for row in rows),
        aliases=sum(row.sheet_name == _SHEETS[1] for row in rows),
        valid_rows=sum(row.status == "VALID" for row in rows),
        invalid_rows=sum(row.status == "INVALID" for row in rows),
        duplicate_rows=duplicate_rows,
        rows=rows,
        warnings=warnings,
    )


@router.get(
    "/section-alias-profiles",
    response_model=ApiResponse[SectionAliasProfileListResponse],
)
async def list_section_alias_profiles(
    session: Session,
    user: MasterDataViewer,
    metadata: Metadata,
    search: Annotated[str | None, Query(max_length=500)] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
    sort_by: Annotated[
        Literal[
            "code",
            "name",
            "isDefault",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "code",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[SectionAliasProfileListResponse]:
    data = await _profile_service(session, user, metadata).list(
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Section alias profiles retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-alias-profiles",
    response_model=ApiResponse[SectionAliasProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_section_alias_profile(
    payload: SectionAliasProfileCreate,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasProfileResponse]:
    data = await _profile_service(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Section alias profile created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/section-alias-profiles/{profile_id}",
    response_model=ApiResponse[SectionAliasProfileResponse],
)
async def get_section_alias_profile(
    profile_id: UUID,
    session: Session,
    user: MasterDataViewer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasProfileResponse]:
    data = await _profile_service(session, user, metadata).get(profile_id)
    return ApiResponse(
        success=True,
        message="Section alias profile retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/section-alias-profiles/{profile_id}",
    response_model=ApiResponse[SectionAliasProfileResponse],
)
async def update_section_alias_profile(
    profile_id: UUID,
    payload: SectionAliasProfileUpdate,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasProfileResponse]:
    data = await _profile_service(session, user, metadata).update(
        profile_id,
        payload,
    )
    return ApiResponse(
        success=True,
        message="Section alias profile updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-alias-profiles/{profile_id}/activate",
    response_model=ApiResponse[SectionAliasProfileResponse],
)
async def activate_section_alias_profile(
    profile_id: UUID,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasProfileResponse]:
    data = await _profile_service(session, user, metadata).update(
        profile_id,
        SectionAliasProfileUpdate(is_active=True),
    )
    return ApiResponse(
        success=True,
        message="Section alias profile activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-alias-profiles/{profile_id}/deactivate",
    response_model=ApiResponse[SectionAliasProfileResponse],
)
async def deactivate_section_alias_profile(
    profile_id: UUID,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasProfileResponse]:
    data = await _profile_service(session, user, metadata).update(
        profile_id,
        SectionAliasProfileUpdate(is_active=False),
    )
    return ApiResponse(
        success=True,
        message="Section alias profile deactivated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-definitions/test-match",
    response_model=ApiResponse[SectionMatchTestResponse],
)
async def test_section_heading_match(
    payload: SectionMatchTestRequest,
    session: Session,
    settings: Configuration,
    user: MasterDataViewer,
    metadata: Metadata,
) -> ApiResponse[SectionMatchTestResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).test_match(payload)
    return ApiResponse(
        success=True,
        message="Section heading match tested successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-definitions/import/preview",
    response_model=ApiResponse[SectionAliasImportTokenResponse],
)
async def preview_section_alias_import(
    file: Annotated[UploadFile, File()],
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
    profile_id: Annotated[
        UUID | None,
        Form(alias="profileId"),
    ] = None,
) -> ApiResponse[SectionAliasImportTokenResponse]:
    if Path(file.filename or "").suffix.casefold() != ".xlsx":
        await file.close()
        raise business_error(
            "Only .xlsx section alias imports are accepted.",
            field="file",
        )
    maximum = settings.request_body_max_size_bytes
    try:
        content = await file.read(maximum + 1)
    finally:
        await file.close()
    if len(content) > maximum:
        raise ApplicationError(
            "Section alias import exceeds the configured size limit.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            errors=[
                ErrorDetail(
                    field="file",
                    message="Upload a smaller XLSX workbook.",
                )
            ],
        )
    service = _transfer_service(session, settings, user, metadata)
    profile, used_default = await _resolve_profile(
        service,
        profile_id,
        require_active=True,
    )
    preview = await service.preview_import(profile.id, content)
    preview = _with_reference_errors(preview, profile)
    import_token = _encode_import_token(settings, user, preview)
    data = _preview_response(
        preview=preview,
        profile=profile,
        import_token=import_token,
        used_default=used_default,
    )
    return ApiResponse(
        success=True,
        message="Section alias import preview generated successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-definitions/import/confirm",
    response_model=ApiResponse[SectionAliasImportConfirmResponse],
)
async def confirm_section_alias_import(
    payload: SectionAliasImportConfirmRequest,
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasImportConfirmResponse]:
    preview = _decode_import_token(settings, user, payload.import_token)
    imported = await _transfer_service(
        session,
        settings,
        user,
        metadata,
    ).confirm_import(preview, mode=payload.mode)
    created = imported.definitions_created + imported.aliases_created
    updated = imported.definitions_updated + imported.aliases_updated
    data = SectionAliasImportConfirmResponse(
        total_rows=created + updated + imported.skipped,
        created=created,
        updated=updated,
        skipped=imported.skipped,
        failed=0,
    )
    return ApiResponse(
        success=True,
        message=(
            "Section definitions and aliases imported successfully "
            f"using {payload.mode.value} mode."
        ),
        data=data,
        errors=None,
    )


@router.get("/section-definitions/export")
async def export_section_aliases(
    session: Session,
    settings: Configuration,
    user: MasterDataViewer,
    metadata: Metadata,
    profile_id: Annotated[
        UUID | None,
        Query(alias="profileId"),
    ] = None,
) -> StreamingResponse:
    service = _transfer_service(session, settings, user, metadata)
    profile, _ = await _resolve_profile(
        service,
        profile_id,
        require_active=False,
    )
    content = await service.export_profile(profile.id)
    filename = (
        f"section_aliases_{profile.code}_"
        f"{datetime.now(UTC).date().isoformat()}.xlsx"
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=XLSX_CONTENT_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get(
    "/section-definitions",
    response_model=ApiResponse[SectionDefinitionListResponse],
)
async def list_section_definitions(
    session: Session,
    user: MasterDataViewer,
    metadata: Metadata,
    profile_id: Annotated[
        UUID | None,
        Query(alias="profileId"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    is_required_default: Annotated[
        bool | None,
        Query(alias="isRequiredDefault"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 50,
    sort_by: Annotated[
        Literal[
            "canonicalCode",
            "displayName",
            "displayOrder",
            "isRequiredDefault",
            "isRepeatable",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "displayOrder",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
) -> ApiResponse[SectionDefinitionListResponse]:
    data = await _definition_service(session, user, metadata).list(
        profile_id=profile_id,
        search=search,
        is_active=is_active,
        is_required_default=is_required_default,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Section definitions retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-definitions",
    response_model=ApiResponse[SectionDefinitionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_section_definition(
    payload: SectionDefinitionCreate,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionDefinitionResponse]:
    data = await _definition_service(session, user, metadata).create(payload)
    return ApiResponse(
        success=True,
        message="Section definition created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/section-definitions/{definition_id}",
    response_model=ApiResponse[SectionDefinitionResponse],
)
async def get_section_definition(
    definition_id: UUID,
    session: Session,
    user: MasterDataViewer,
    metadata: Metadata,
) -> ApiResponse[SectionDefinitionResponse]:
    data = await _definition_service(session, user, metadata).get(
        definition_id
    )
    return ApiResponse(
        success=True,
        message="Section definition retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/section-definitions/{definition_id}",
    response_model=ApiResponse[SectionDefinitionResponse],
)
async def update_section_definition(
    definition_id: UUID,
    payload: SectionDefinitionUpdate,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionDefinitionResponse]:
    data = await _definition_service(session, user, metadata).update(
        definition_id,
        payload,
    )
    return ApiResponse(
        success=True,
        message="Section definition updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-definitions/{definition_id}/activate",
    response_model=ApiResponse[SectionDefinitionResponse],
)
async def activate_section_definition(
    definition_id: UUID,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionDefinitionResponse]:
    data = await _definition_service(session, user, metadata).update(
        definition_id,
        SectionDefinitionUpdate(is_active=True),
    )
    return ApiResponse(
        success=True,
        message="Section definition activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-definitions/{definition_id}/deactivate",
    response_model=ApiResponse[SectionDefinitionResponse],
)
async def deactivate_section_definition(
    definition_id: UUID,
    session: Session,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionDefinitionResponse]:
    data = await _definition_service(session, user, metadata).update(
        definition_id,
        SectionDefinitionUpdate(is_active=False),
    )
    return ApiResponse(
        success=True,
        message="Section definition deactivated successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/section-aliases",
    response_model=ApiResponse[SectionAliasListResponse],
)
async def list_section_aliases(
    session: Session,
    settings: Configuration,
    user: MasterDataViewer,
    metadata: Metadata,
    profile_id: Annotated[
        UUID | None,
        Query(alias="profileId"),
    ] = None,
    section_definition_id: Annotated[
        UUID | None,
        Query(alias="sectionDefinitionId"),
    ] = None,
    language_code: Annotated[
        SectionAliasLanguageCode | None,
        Query(alias="languageCode"),
    ] = None,
    match_type: Annotated[
        SectionAliasMatchType | None,
        Query(alias="matchType"),
    ] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=500),
    ] = 50,
    sort_by: Annotated[
        Literal[
            "aliasText",
            "languageCode",
            "matchType",
            "priority",
            "isActive",
            "createdAt",
            "updatedAt",
        ],
        Query(alias="sortBy"),
    ] = "priority",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "desc",
) -> ApiResponse[SectionAliasListResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).list(
        profile_id=profile_id,
        section_definition_id=section_definition_id,
        language_code=language_code,
        match_type=match_type,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        success=True,
        message="Section aliases retrieved successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/section-aliases",
    response_model=ApiResponse[SectionAliasResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_section_alias(
    payload: SectionAliasCreate,
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).create(payload)
    return ApiResponse(
        success=True,
        message="Section alias created successfully.",
        data=data,
        errors=None,
    )


@router.get(
    "/section-aliases/{alias_id}",
    response_model=ApiResponse[SectionAliasResponse],
)
async def get_section_alias(
    alias_id: UUID,
    session: Session,
    settings: Configuration,
    user: MasterDataViewer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).get(alias_id)
    return ApiResponse(
        success=True,
        message="Section alias retrieved successfully.",
        data=data,
        errors=None,
    )


@router.put(
    "/section-aliases/{alias_id}",
    response_model=ApiResponse[SectionAliasResponse],
)
async def update_section_alias(
    alias_id: UUID,
    payload: SectionAliasUpdate,
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).update(alias_id, payload)
    return ApiResponse(
        success=True,
        message="Section alias updated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-aliases/{alias_id}/activate",
    response_model=ApiResponse[SectionAliasResponse],
)
async def activate_section_alias(
    alias_id: UUID,
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).update(alias_id, SectionAliasUpdate(is_active=True))
    return ApiResponse(
        success=True,
        message="Section alias activated successfully.",
        data=data,
        errors=None,
    )


@router.patch(
    "/section-aliases/{alias_id}/deactivate",
    response_model=ApiResponse[SectionAliasResponse],
)
async def deactivate_section_alias(
    alias_id: UUID,
    session: Session,
    settings: Configuration,
    user: SectionConfigurer,
    metadata: Metadata,
) -> ApiResponse[SectionAliasResponse]:
    data = await _alias_service(
        session,
        settings,
        user,
        metadata,
    ).update(alias_id, SectionAliasUpdate(is_active=False))
    return ApiResponse(
        success=True,
        message="Section alias deactivated successfully.",
        data=data,
        errors=None,
    )

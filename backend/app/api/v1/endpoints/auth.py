"""Thin HTTP endpoints for authentication use cases."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import (
    get_auth_service,
    get_current_active_user,
    get_request_metadata,
)
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.schemas.common import ApiResponse
from app.services.auth.auth_service import AuthService, RequestMetadata

router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate a user",
)
async def login(
    payload: LoginRequest,
    metadata: Annotated[RequestMetadata, Depends(get_request_metadata)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    data = await service.login(payload, metadata)
    return ApiResponse(
        success=True,
        message="Login successful.",
        data=data,
        errors=None,
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Rotate a refresh token",
)
async def refresh(
    payload: TokenRefreshRequest,
    metadata: Annotated[RequestMetadata, Depends(get_request_metadata)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    data = await service.refresh(payload.refresh_token, metadata)
    return ApiResponse(
        success=True,
        message="Token refreshed successfully.",
        data=data,
        errors=None,
    )


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Revoke a refresh token",
)
async def logout(
    payload: LogoutRequest,
    metadata: Annotated[RequestMetadata, Depends(get_request_metadata)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[None]:
    await service.logout(payload.refresh_token, metadata)
    return ApiResponse(
        success=True,
        message="Logout successful.",
        data=None,
        errors=None,
    )


@router.get(
    "/me",
    response_model=ApiResponse[CurrentUserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get the current user",
)
async def current_user(
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[CurrentUserResponse]:
    return ApiResponse(
        success=True,
        message="Current user retrieved successfully.",
        data=service.current_user(user),
        errors=None,
    )

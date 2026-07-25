"""JWT creation and validation tests."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.authorization import UserRole
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.services.auth.token_service import TokenService


@pytest.fixture
def token_user() -> User:
    return User(
        id=uuid4(),
        name="Token User",
        email="token@example.com",
        password_hash="not-used",
        role=UserRole.REVIEWER,
        is_active=True,
        is_superuser=False,
    )


def test_access_token_contains_required_claims(
    token_service: TokenService,
    token_user: User,
) -> None:
    token = token_service.create_access_token(token_user)
    claims = token_service.decode_token(token, expected_type="access")

    assert claims["sub"] == str(token_user.id)
    assert claims["email"] == token_user.email
    assert claims["role"] == UserRole.REVIEWER.value
    assert claims["type"] == "access"
    assert claims["iat"] < claims["exp"]
    assert claims["jti"]


def test_refresh_token_can_be_created_and_decoded(
    token_service: TokenService,
    token_user: User,
) -> None:
    token = token_service.create_refresh_token(token_user)
    claims = token_service.decode_token(token, expected_type="refresh")

    assert claims["sub"] == str(token_user.id)
    assert claims["type"] == "refresh"
    assert token_service.verify_token_hash(
        token,
        token_service.hash_token(token),
    )
    access_replacement, refresh_replacement = (
        token_service.rotate_refresh_token(token, token_user)
    )
    assert (
        token_service.decode_token(
            access_replacement,
            expected_type="access",
        )["sub"]
        == str(token_user.id)
    )
    assert refresh_replacement != token
    assert token_service.revoke_refresh_token(token) == (
        token_service.hash_token(token)
    )


def test_token_type_is_validated(
    token_service: TokenService,
    token_user: User,
) -> None:
    access_token = token_service.create_access_token(token_user)

    with pytest.raises(AuthenticationError):
        token_service.decode_token(access_token, expected_type="refresh")


def test_refresh_rotation_rejects_a_different_user(
    token_service: TokenService,
    token_user: User,
) -> None:
    token = token_service.create_refresh_token(token_user)
    other_user = User(
        id=uuid4(),
        name="Other User",
        email="other@example.com",
        password_hash="not-used",
        role=UserRole.VIEWER,
        is_active=True,
        is_superuser=False,
    )

    with pytest.raises(AuthenticationError) as exception:
        token_service.rotate_refresh_token(token, other_user)

    assert exception.value.errors is not None
    assert (
        exception.value.errors[0].message
        == "Refresh token subject is invalid."
    )


def test_expired_token_is_rejected(
    token_service: TokenService,
    token_user: User,
) -> None:
    token = token_service.create_access_token(
        token_user,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(AuthenticationError) as exception:
        token_service.decode_token(token, expected_type="access")
    assert exception.value.status_code == 401
    assert exception.value.errors is not None
    assert exception.value.errors[0].message == "Token has expired."


def test_invalid_token_is_rejected(token_service: TokenService) -> None:
    with pytest.raises(AuthenticationError) as exception:
        token_service.decode_token("not-a-jwt", expected_type="access")
    assert exception.value.status_code == 401
    assert exception.value.errors is not None
    assert exception.value.errors[0].message == "Token is invalid."

"""Argon2 password policy and verification tests."""

import pytest

from app.services.auth.password_service import PasswordService


def test_password_can_be_hashed_and_verified(
    password_service: PasswordService,
) -> None:
    encoded = password_service.hash_password("Valid123")

    assert encoded != "Valid123"
    assert encoded.startswith("$argon2id$")
    assert password_service.verify_password("Valid123", encoded) is True


def test_wrong_password_is_rejected(
    password_service: PasswordService,
) -> None:
    encoded = password_service.hash_password("Valid123")

    assert password_service.verify_password("Wrong123", encoded) is False
    assert password_service.verify_password("Valid123", "malformed") is False


def test_dummy_verification_uses_argon2(
    password_service: PasswordService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_hashes: list[str] = []
    original_verify = password_service.verify_password

    def capture_verify(password: str, password_hash: str) -> bool:
        verified_hashes.append(password_hash)
        return original_verify(password, password_hash)

    monkeypatch.setattr(password_service, "verify_password", capture_verify)

    password_service.consume_dummy_verification("Unknown123")

    assert verified_hashes[0].startswith("$argon2id$")


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Short1", "8 characters"),
        ("lowercase1", "uppercase"),
        ("UPPERCASE1", "lowercase"),
        ("NoNumbers", "number"),
    ],
)
def test_weak_password_is_rejected(
    password_service: PasswordService,
    password: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        password_service.validate_password_strength(password)

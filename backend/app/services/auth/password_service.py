"""Argon2id password hashing and verification."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$Z9bTltS7D45MzEht+xxFeg"
    "$HvulGUYzOsDISUfqTV+kgqzY0mryjhkV0aRsC1JMIMk"
)


class PasswordService:
    """Hash passwords and safely verify untrusted login credentials."""

    def __init__(self, password_hasher: PasswordHasher | None = None) -> None:
        self._password_hasher = password_hasher or PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> str:
        """Return an Argon2id encoded hash for a non-empty password."""

        if not password:
            raise ValueError("Password must not be empty.")
        return self._password_hasher.hash(password)

    @staticmethod
    def validate_password_strength(password: str) -> None:
        """Enforce the Phase 2 minimum password policy."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(character.isupper() for character in password):
            raise ValueError(
                "Password must contain at least one uppercase letter."
            )
        if not any(character.islower() for character in password):
            raise ValueError(
                "Password must contain at least one lowercase letter."
            )
        if not any(character.isdigit() for character in password):
            raise ValueError("Password must contain at least one number.")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Return false for mismatches and malformed or unsupported hashes."""

        if not password or not password_hash:
            return False
        try:
            return self._password_hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError):
            return False

    def consume_dummy_verification(self, password: str) -> None:
        """Perform one Argon2 verification when no real account hash exists."""

        self.verify_password(password, _DUMMY_PASSWORD_HASH)

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether a valid encoded hash uses outdated parameters."""

        if not password_hash:
            return True
        try:
            return self._password_hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True

    def verify_and_update(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]:
        """Verify a password and return a stronger replacement hash if needed."""

        if not self.verify_password(password, password_hash):
            return False, None
        if self.needs_rehash(password_hash):
            return True, self.hash_password(password)
        return True, None

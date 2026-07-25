"""Create the default Super Admin account idempotently.

Run from the backend directory with:

    python -m scripts.create_admin
"""

import asyncio

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.database.session import AsyncSessionFactory
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth.password_service import PasswordService


async def create_admin() -> bool:
    """Create one environment-configured administrator if it does not exist."""
    settings = get_settings()
    if settings.default_admin_password is None:
        raise RuntimeError(
            "DEFAULT_ADMIN_PASSWORD is required to create the administrator."
        )

    email = settings.default_admin_email.strip().lower()
    password = settings.default_admin_password.get_secret_value()
    password_service = PasswordService()
    password_service.validate_password_strength(password)

    async with AsyncSessionFactory() as session:
        repository = UserRepository(session)
        existing = await repository.get_by_email(email, include_deleted=True)
        if existing is not None:
            if (
                existing.deleted_at is not None
                or not existing.is_active
                or not existing.is_superuser
                or existing.role is not UserRole.SUPER_ADMIN
            ):
                raise RuntimeError(
                    "DEFAULT_ADMIN_EMAIL belongs to an account that is not "
                    "an active Super Admin."
                )
            print(f"Administrator already exists: {email}")
            return False

        administrator = User(
            name=settings.default_admin_name.strip(),
            email=email,
            password_hash=password_service.hash_password(password),
            role=UserRole.SUPER_ADMIN,
            department_id=None,
            is_active=True,
            is_superuser=True,
        )
        await repository.add(administrator)
        await session.commit()

    print(f"Administrator created successfully: {email}")
    return True


def main() -> None:
    """Synchronous CLI entry point."""
    asyncio.run(create_admin())


if __name__ == "__main__":
    main()

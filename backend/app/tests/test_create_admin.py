"""Default administrator bootstrap tests."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import pytest

from app.core.authorization import UserRole
from app.models.user import User
from app.services.auth.password_service import PasswordService
from scripts import create_admin as admin_script

TestSessionFactory = async_sessionmaker[AsyncSession]


@pytest.mark.asyncio
async def test_create_admin_is_idempotent_and_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    session_factory: TestSessionFactory,
    password_service: PasswordService,
) -> None:
    monkeypatch.setattr(admin_script, "AsyncSessionFactory", session_factory)
    monkeypatch.setattr(
        admin_script,
        "PasswordService",
        lambda: password_service,
    )

    first_created = await admin_script.create_admin()
    second_created = await admin_script.create_admin()

    assert first_created is True
    assert second_created is False
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(User))
        result = await session.execute(select(User))
        user = result.scalar_one()
    assert count == 1
    assert user.email == "admin@example.com"
    assert user.role is UserRole.SUPER_ADMIN
    assert user.is_active is True
    assert user.is_superuser is True

    output = capsys.readouterr().out
    assert "Admin123" not in output
    assert "$argon2" not in output


@pytest.mark.asyncio
async def test_create_admin_rejects_conflicting_existing_account(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: TestSessionFactory,
) -> None:
    monkeypatch.setattr(admin_script, "AsyncSessionFactory", session_factory)
    async with session_factory() as session:
        session.add(
            User(
                name="Existing Viewer",
                email="admin@example.com",
                password_hash="not-used",
                role=UserRole.VIEWER,
                is_active=True,
                is_superuser=False,
            )
        )
        await session.commit()

    with pytest.raises(RuntimeError, match="not an active Super Admin"):
        await admin_script.create_admin()

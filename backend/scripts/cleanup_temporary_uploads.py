"""Clean expired Phase 5 upload sessions and temporary files.

Run from the backend directory with:

    python -m scripts.cleanup_temporary_uploads
"""

import asyncio

from app.database.session import AsyncSessionFactory, dispose_engine
from app.services.documents.upload_cleanup_service import (
    UploadCleanupService,
)


async def cleanup_temporary_uploads() -> None:
    try:
        async with AsyncSessionFactory() as session:
            summary = await UploadCleanupService(session).cleanup_expired()
        print("Temporary upload cleanup completed.")
        print(f"Sessions scanned: {summary.scanned_sessions}")
        print(f"Sessions expired: {summary.expired_sessions}")
        print(f"Temporary files deleted: {summary.deleted_files}")
        print(f"Sessions failed: {summary.failed_sessions}")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(cleanup_temporary_uploads())


if __name__ == "__main__":
    main()

"""Sync all users from the database to Google Sheets.

Reads every active user from the DB and upserts their row in Google Sheets
using the same mapping logic used by the automatic post-transition hook.

# uv run python scripts/sync_db_to_sheets.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatbot.db.services import services
from chatbot.services.google_sheets_sync import sync_user_to_sheets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await services.database.connect()
    try:
        users = await services.get_all_users()
        total = len(users)
        logger.info("Found %d users in the database.", total)

        success = 0
        failed = 0
        for user in users:
            phone: str = user.phone  # type: ignore[attr-defined]
            try:
                await sync_user_to_sheets(phone)
                success += 1
            except Exception as exc:
                logger.error("Failed to sync phone=%s: %s", phone, exc)
                failed += 1

        logger.info(
            "Sync complete. Total: %d | OK: %d | Failed: %d",
            total,
            success,
            failed,
        )
    finally:
        await services.database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

"""Sheets sync worker — bulk-syncs all users from DB to Google Sheets."""

from __future__ import annotations

import logging

from chatbot.db.services import services
from chatbot.services.google_sheets_sync import sync_user_to_sheets

logger = logging.getLogger(__name__)


async def run() -> None:
    """Sync every user in the DB to Google Sheets."""
    logger.info("[sheets_sync_worker] Starting run")
    users = await services.get_all_users()
    total = len(users)
    success = 0
    failed = 0

    for user in users:
        phone: str = user.phone  # type: ignore[attr-defined]
        try:
            await sync_user_to_sheets(phone)
            success += 1
        except Exception as exc:
            logger.error("[sheets_sync_worker] Failed phone=%s: %s", phone, exc)
            failed += 1

    logger.info(
        "[sheets_sync_worker] Done. Total=%d OK=%d Failed=%d",
        total,
        success,
        failed,
    )

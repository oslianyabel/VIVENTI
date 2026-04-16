"""Scheduler — runs background workers every 15 minutes."""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_SECONDS: int = 900  # 15 minutes
SHEETS_SYNC_INTERVAL_SECONDS: int = 1800  # 30 minutes

_sheets_sync_tick: int = 0


async def _run_tick() -> None:
    """Execute all background workers for a single tick."""
    global _sheets_sync_tick

    from chatbot.reminders.demo_reminder_worker import run as run_demo_reminders
    from chatbot.reminders.follow_up_worker import run as run_follow_ups
    from chatbot.reminders.sheets_sync_worker import run as run_sheets_sync

    tick_start = time.monotonic()
    logger.info("[scheduler] Tick started")

    try:
        await run_follow_ups()
    except Exception as exc:
        logger.error("[scheduler] follow_up_worker failed: %s", exc, exc_info=True)

    try:
        await run_demo_reminders()
    except Exception as exc:
        logger.error("[scheduler] demo_reminder_worker failed: %s", exc, exc_info=True)

    _sheets_sync_tick += SCHEDULER_INTERVAL_SECONDS
    if _sheets_sync_tick >= SHEETS_SYNC_INTERVAL_SECONDS:
        _sheets_sync_tick = 0
        try:
            await run_sheets_sync()
        except Exception as exc:
            logger.error(
                "[scheduler] sheets_sync_worker failed: %s", exc, exc_info=True
            )

    elapsed = time.monotonic() - tick_start
    logger.info("[scheduler] Tick completed in %.1fs", elapsed)


async def _scheduler_loop() -> None:
    """Loop that runs workers every SCHEDULER_INTERVAL_SECONDS."""
    logger.info("[scheduler] Started — interval=%ds", SCHEDULER_INTERVAL_SECONDS)
    while True:
        await _run_tick()
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


async def start_scheduler() -> asyncio.Task:
    """Start the scheduler as a background asyncio task.

    Returns:
        The asyncio.Task running the scheduler loop.
    """
    task = asyncio.create_task(_scheduler_loop())
    logger.info("[scheduler] Background task created")
    return task

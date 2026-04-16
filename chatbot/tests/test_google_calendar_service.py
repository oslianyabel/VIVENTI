# uv run pytest -s chatbot/tests/test_google_calendar_service.py
"""Integration tests for Google Calendar service — real API calls.

These tests create, read, update and delete events on the real Google
Calendar configured via environment variables.  They must run sequentially
because later tests depend on the event created by the first one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from chatbot.domain.demo import DemoRecord
from chatbot.services.google_calendar_service import (
    cancel_event,
    create_event,
    find_available_slots,
    get_event,
    list_busy_slots,
    update_event,
)

logger = logging.getLogger(__name__)

# Use a date far in the future to avoid collisions with real demos
_TEST_BASE_DT = datetime(2029, 12, 15, 10, 0, tzinfo=timezone.utc)
_TEST_PHONE = "+0000000000"

# Shared state across ordered tests
_created_event_id: str | None = None


def _make_demo(scheduled_at: datetime | None = None) -> DemoRecord:
    return DemoRecord(
        title="TEST — Demo de prueba (borrar si queda)",
        duration_minutes=30,
        description="Evento creado automáticamente por test suite. Se elimina al final.",
        user_phone=_TEST_PHONE,
        scheduled_at=scheduled_at or _TEST_BASE_DT,
    )


# ── 1. list_busy_slots ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_busy_slots_returns_list() -> None:
    """list_busy_slots should return a list (possibly empty) without errors."""
    day_start = _TEST_BASE_DT.replace(hour=0, minute=0, second=0)
    day_end = day_start + timedelta(days=1)

    result = await list_busy_slots(day_start, day_end)

    assert isinstance(result, list)
    print(f"[OK] list_busy_slots returned {len(result)} busy slot(s)")


# ── 2. find_available_slots ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_available_slots_returns_list() -> None:
    """find_available_slots should return available datetime slots."""
    day_start = _TEST_BASE_DT.replace(hour=0, minute=0, second=0)
    day_end = day_start + timedelta(days=1)

    slots = await find_available_slots(day_start, day_end)

    assert isinstance(slots, list)
    for slot in slots:
        assert isinstance(slot, datetime)
    print(f"[OK] find_available_slots returned {len(slots)} slot(s)")


# ── 3. create_event ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_event_returns_event_id() -> None:
    """create_event should return a valid event ID string."""
    global _created_event_id

    demo = _make_demo()
    event_id = await create_event(demo, attendee_email=None)

    assert isinstance(event_id, str)
    assert len(event_id) > 0
    _created_event_id = event_id
    print(f"[OK] create_event returned event_id={event_id}")


# ── 4. get_event ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_event_returns_details() -> None:
    """get_event should return event details for the created event."""
    assert _created_event_id is not None, "Requires test_create_event to run first"

    event = await get_event(_created_event_id)

    assert isinstance(event, dict)
    assert event.get("id") == _created_event_id
    assert "summary" in event
    print(f"[OK] get_event returned summary='{event.get('summary')}'")


# ── 5. update_event ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_event_changes_datetime() -> None:
    """update_event should successfully patch the event to a new time."""
    assert _created_event_id is not None, "Requires test_create_event to run first"

    new_dt = _TEST_BASE_DT + timedelta(hours=2)
    demo = _make_demo(scheduled_at=new_dt)
    demo.google_calendar_event_id = _created_event_id

    returned_id = await update_event(_created_event_id, new_dt, demo)

    assert returned_id == _created_event_id

    # Verify change — parse the datetime to compare in UTC
    event = await get_event(_created_event_id)
    start_str = event["start"]["dateTime"]
    start_parsed = datetime.fromisoformat(start_str).astimezone(timezone.utc)
    assert start_parsed.hour == 12  # moved from 10:00 to 12:00 UTC
    print(
        f"[OK] update_event moved event to {start_str} (UTC hour={start_parsed.hour})"
    )


# ── 6. cancel_event ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_event_deletes() -> None:
    """cancel_event should delete the event from Google Calendar."""
    assert _created_event_id is not None, "Requires test_create_event to run first"

    await cancel_event(_created_event_id)

    # Google Calendar marks deleted events as 'cancelled' rather than
    # removing them immediately, so get_event still works but status changes.
    event = await get_event(_created_event_id)
    assert event.get("status") == "cancelled"

    print(f"[OK] cancel_event set event {_created_event_id} to cancelled")


# ── 7. cancel_event idempotent (410 already gone) ──────────────────────────


@pytest.mark.asyncio
async def test_cancel_event_already_deleted_does_not_raise() -> None:
    """cancel_event on an already-deleted event should not raise."""
    assert _created_event_id is not None, "Requires test_create_event to run first"

    # Should not raise — the service handles 410 gracefully
    await cancel_event(_created_event_id)
    print("[OK] cancel_event on already-deleted event did not raise")

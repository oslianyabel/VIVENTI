"""Google Calendar API wrapper service.

Provides async functions for managing demo events via Google Calendar API v3
using a service account.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from chatbot.core.config import config
from chatbot.domain.demo import DemoRecord

logger = logging.getLogger(__name__)

DEMO_DURATION_MINUTES: int = 30
BUSINESS_HOURS_START: int = 9
BUSINESS_HOURS_END: int = 18
SCOPES: list[str] = ["https://www.googleapis.com/auth/calendar"]
API_TIMEOUT: int = 15


class GoogleCalendarError(Exception):
    """Wraps HttpError from the Google Calendar API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


def _get_calendar_service():
    """Build and return the Google Calendar API service."""
    credentials = Credentials.from_service_account_file(
        config.GOOGLE_SHEETS_CREDENTIALS_FILE,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=credentials)


async def _run_in_executor(func, *args):
    """Run a blocking Google API call in the default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


async def list_busy_slots(
    date_start: datetime,
    date_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """Return busy time intervals in the calendar between date_start and date_end.

    Args:
        date_start: Start of the time range (timezone-aware).
        date_end: End of the time range (timezone-aware).

    Returns:
        List of (start, end) tuples representing busy intervals.
    """
    service = _get_calendar_service()
    calendar_id = config.GOOGLE_CALENDAR_ID

    def _fetch():
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=date_start.isoformat(),
                timeMax=date_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return events_result.get("items", [])

    try:
        events = await _run_in_executor(_fetch)
    except HttpError as exc:
        raise GoogleCalendarError(
            f"Failed to list events: {exc}", status_code=exc.resp.status
        ) from exc

    busy: list[tuple[datetime, datetime]] = []
    for event in events:
        start_str = event["start"].get("dateTime", event["start"].get("date"))
        end_str = event["end"].get("dateTime", event["end"].get("date"))
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        busy.append((start, end))

    return busy


async def find_available_slots(
    date_start: datetime,
    date_end: datetime,
    duration_minutes: int = DEMO_DURATION_MINUTES,
) -> list[datetime]:
    """Compute available time slots within business hours.

    Args:
        date_start: Start of the search range (timezone-aware).
        date_end: End of the search range (timezone-aware).
        duration_minutes: Duration of each required slot in minutes.

    Returns:
        List of available slot start times.
    """
    busy_slots = await list_busy_slots(date_start, date_end)
    tz = date_start.tzinfo or timezone.utc

    available: list[datetime] = []
    current_date = date_start.date()
    end_date = date_end.date()

    while current_date <= end_date:
        day_start = datetime(
            current_date.year,
            current_date.month,
            current_date.day,
            BUSINESS_HOURS_START,
            0,
            tzinfo=tz,
        )
        day_end = datetime(
            current_date.year,
            current_date.month,
            current_date.day,
            BUSINESS_HOURS_END,
            0,
            tzinfo=tz,
        )

        slot_start = day_start
        while slot_start + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            is_free = True
            for busy_start, busy_end in busy_slots:
                if slot_start < busy_end and slot_end > busy_start:
                    is_free = False
                    break
            if is_free:
                available.append(slot_start)
            slot_start += timedelta(minutes=30)

        current_date += timedelta(days=1)

    return available


async def create_event(
    demo: DemoRecord,
    attendee_email: str | None = None,
) -> str:
    """Create a Google Calendar event for a demo.

    Args:
        demo: DemoRecord with the demo details.
        attendee_email: Optional email to add as attendee.

    Returns:
        The Google Calendar event ID.
    """
    service = _get_calendar_service()
    calendar_id = config.GOOGLE_CALENDAR_ID

    start_dt = demo.scheduled_at
    end_dt = start_dt + timedelta(minutes=demo.duration_minutes)

    event_body: dict[str, Any] = {
        "summary": demo.title,
        "description": demo.description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
    }
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]

    def _insert():
        return (
            service.events().insert(calendarId=calendar_id, body=event_body).execute()
        )

    try:
        created = await _run_in_executor(_insert)
    except HttpError as exc:
        raise GoogleCalendarError(
            f"Failed to create event: {exc}", status_code=exc.resp.status
        ) from exc

    event_id: str = created["id"]
    logger.info("[google_calendar] Created event %s for %s", event_id, demo.user_phone)
    return event_id


async def update_event(
    event_id: str,
    new_start: datetime,
    demo: DemoRecord,
    attendee_email: str | None = None,
) -> str:
    """Update an existing Google Calendar event.

    Args:
        event_id: The Google Calendar event ID to update.
        new_start: The new start datetime.
        demo: DemoRecord with updated details.
        attendee_email: Optional email to add as attendee.

    Returns:
        The event ID.
    """
    service = _get_calendar_service()
    calendar_id = config.GOOGLE_CALENDAR_ID

    end_dt = new_start + timedelta(minutes=demo.duration_minutes)

    patch_body: dict[str, Any] = {
        "summary": demo.title,
        "description": demo.description,
        "start": {"dateTime": new_start.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
    }
    if attendee_email:
        patch_body["attendees"] = [{"email": attendee_email}]

    def _patch():
        return (
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=patch_body)
            .execute()
        )

    try:
        await _run_in_executor(_patch)
    except HttpError as exc:
        raise GoogleCalendarError(
            f"Failed to update event {event_id}: {exc}",
            status_code=exc.resp.status,
        ) from exc

    logger.info("[google_calendar] Updated event %s", event_id)
    return event_id


async def cancel_event(event_id: str) -> None:
    """Delete a Google Calendar event.

    Args:
        event_id: The Google Calendar event ID to delete.
    """
    service = _get_calendar_service()
    calendar_id = config.GOOGLE_CALENDAR_ID

    def _delete():
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

    try:
        await _run_in_executor(_delete)
    except HttpError as exc:
        if exc.resp.status == 410:
            logger.warning("[google_calendar] Event %s already deleted", event_id)
            return
        raise GoogleCalendarError(
            f"Failed to delete event {event_id}: {exc}",
            status_code=exc.resp.status,
        ) from exc

    logger.info("[google_calendar] Cancelled event %s", event_id)


async def get_event(event_id: str) -> dict[str, Any]:
    """Retrieve event details from Google Calendar.

    Args:
        event_id: The Google Calendar event ID.

    Returns:
        The event resource dict.
    """
    service = _get_calendar_service()
    calendar_id = config.GOOGLE_CALENDAR_ID

    def _get():
        return service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    try:
        return await _run_in_executor(_get)
    except HttpError as exc:
        raise GoogleCalendarError(
            f"Failed to get event {event_id}: {exc}",
            status_code=exc.resp.status,
        ) from exc

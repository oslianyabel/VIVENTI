from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DemoRecord:
    title: str
    duration_minutes: int
    description: str
    user_phone: str
    scheduled_at: datetime
    google_calendar_event_id: str | None = None
    upcoming_reminder_sent_at: datetime | None = None

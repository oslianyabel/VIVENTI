"""Dependency injection container for the AI agent.

Provides all external services the agent needs: ERP client, DB services,
and WhatsApp client.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from chatbot.db.services import Services
from chatbot.messaging.whatsapp import WhatsAppManager


@dataclass
class AgentDeps:
    """Dependencies injected into every agent run via RunContext."""

    db_services: Services
    whatsapp_client: WhatsAppManager
    user_phone: str = ""
    user_name: str | None = None
    user_email: str | None = None
    telegram_id: str | None = None
    # Tracks which tools have been called in the current turn (for once-per-turn enforcement)
    called_tools: set[str] = field(default_factory=set)
    # Channel-specific callback to send a photo (bytes, caption) to the user.
    # Set by each channel handler (WhatsApp / Telegram). None when the channel
    # does not support image delivery from agent tools.
    send_photo_callback: Callable[[bytes, str], Awaitable[None]] | None = field(
        default=None
    )

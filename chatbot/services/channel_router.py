"""Channel router — sends messages via the correct channel based on user data."""

from __future__ import annotations

import logging

from chatbot.api.utils import message_handler
from chatbot.db.services import services
from chatbot.messaging.whatsapp import whatsapp_manager

logger = logging.getLogger(__name__)


async def send_to_user(phone: str, text: str) -> None:
    """Send a message to a user via the appropriate channel and persist it.

    Checks if the user has a stored telegram_id. If yes, sends via Telegram.
    Otherwise sends via WhatsApp.

    Args:
        phone: User phone number or chat identifier.
        text: Message text to send.
    """
    telegram_id: str | None = None

    # Check for Telegram channel marker in messages
    has_telegram = await services.has_message(
        phone=phone, role="system", message="CHANNEL: telegram"
    )

    if has_telegram:
        telegram_id = phone  # In Telegram mode, phone IS the chat_id

    if telegram_id:
        try:
            from telegram import Bot

            from chatbot.core.config import config

            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            async with bot:
                await bot.send_message(chat_id=int(telegram_id), text=text)
            logger.info("[channel_router] Sent via Telegram to %s", telegram_id)
        except Exception as exc:
            logger.error(
                "[channel_router] Telegram send failed for %s: %s",
                telegram_id,
                exc,
            )
            return
    else:
        try:
            await whatsapp_manager.send_text(user_number=phone, text=text)
            logger.info("[channel_router] Sent via WhatsApp to %s", phone)
        except Exception as exc:
            logger.error("[channel_router] WhatsApp send failed for %s: %s", phone, exc)
            return

    # Persist the sent message as assistant message
    await message_handler.save_assistant_msg(phone, text, tools_used=[])

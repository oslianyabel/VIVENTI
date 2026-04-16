"""Direct tool commands for the Telegram bot.

Commands registered:
  /test_dev_notifications
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from chatbot.core.config import config
from chatbot.messaging.telegram_notifier import (
    _build_slow_response_message,
    notify_error,
    send_message,
)

logger = logging.getLogger(__name__)

_MAX_MSG_LEN = 4000


# ---------------------------------------------------------------------------
# /test_dev_notifications
# ---------------------------------------------------------------------------


async def cmd_test_dev_notifications(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/test_dev_notifications — sends developer notification test messages."""
    del context
    if not update.message or not update.effective_chat:
        return

    if not config.TELEGRAM_BOT_TOKEN_NOTIFIER or not config.TELEGRAM_DEV_CHAT_ID:
        await update.message.reply_text(
            "⚠️ Developer Telegram notifications are not configured.",
        )
        return

    chat_id = str(update.effective_chat.id)

    await notify_error(
        RuntimeError("Telegram dev notification test"),
        context=f"telegram_cmd_test | chat_id={chat_id}",
    )

    slow_response_message = _build_slow_response_message(
        phone=chat_id,
        user_message="Developer notification test triggered from Telegram command.",
        tools_used=["notify_error", "_build_slow_response_message"],
        ai_response="This is a synthetic slow-response message generated from /test_dev_notifications.",
        message_datetime=datetime.now(),
        history_count=1,
        response_time=42.0,
        provider_error="Synthetic provider timeout for notifier validation",
    )
    slow_message_sent = await send_message(
        config.TELEGRAM_DEV_CHAT_ID,
        slow_response_message,
        parse_mode="Markdown",
    )

    lines = [
        "Developer notification test completed.",
        "- `notify_error` was triggered.",
        f"- Slow-response test message sent: `{'yes' if slow_message_sent else 'no'}`.",
        f"- Developer chat: `{config.TELEGRAM_DEV_CHAT_ID}`.",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

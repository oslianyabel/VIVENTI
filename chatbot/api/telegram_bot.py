"""Telegram chatbot entry point using the VIVENTI AI agent.

The Telegram chat_id is used as the conversation identifier in the DB and as
``telegram_id`` in AgentDeps.

Run with:
    uv run python scripts/run_telegram_bot.py
"""

from __future__ import annotations

import asyncio
import logging

from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from chatbot.ai_agent import get_viventi_agent
from chatbot.ai_agent.agent import FALLBACK_MODEL
from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.ai_agent.error_agent import run_error_agent
from chatbot.api.utils import message_handler
from chatbot.api.utils.telegram_commands import cmd_test_dev_notifications
from chatbot.api.utils.text import strip_markdown
from chatbot.api.utils.webhook_parser import (
    create_or_retrieve_documents_dir,
    create_or_retrieve_images_dir,
    create_or_retrieve_voice_dir,
)
from chatbot.audio.audio_converter import convert_ogg_to_mp3
from chatbot.audio.stt import AVAILABLE_AUDIO_FORMATS, transcribe_audio
from chatbot.core.config import config
from chatbot.core.logging_conf import init_logging
from chatbot.db.services import services
from chatbot.messaging.telegram_notifier import notify_error
from chatbot.messaging.whatsapp import WhatsAppManager
from chatbot.services.message_processor import pre_agent_processing

logger = logging.getLogger(__name__)

HISTORY_SUMMARY_THRESHOLD: int = 30

CHANNEL_TELEGRAM: str = "telegram"
CHANNEL_WHATSAPP: str = "whatsapp"
CHANNEL_MARKERS: dict[str, str] = {
    CHANNEL_TELEGRAM: "CHANNEL: telegram",
    CHANNEL_WHATSAPP: "CHANNEL: whatsapp",
}

_noop_whatsapp = WhatsAppManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _typing_loop(bot, chat_id: int) -> None:
    """Send 'typing' chat action every 4 s until the task is cancelled."""
    while True:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(4)


def _extract_tools_used(result) -> list[str]:
    from pydantic_ai.messages import ModelResponse, ToolCallPart

    tools: list[str] = []
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    tools.append(part.tool_name)
    return tools


async def _maybe_compress_history(chat_id: str, history_len: int) -> None:
    """Resetea el historial cuando supera el umbral de mensajes."""
    total = history_len + 2  # +1 usuario +1 asistente del turno actual
    if total <= HISTORY_SUMMARY_THRESHOLD:
        return

    logger.info(
        "[history] Resetting history for telegram_id=%s (%d messages > %d threshold)",
        chat_id,
        total,
        HISTORY_SUMMARY_THRESHOLD,
    )
    try:
        await services.reset_chat(chat_id)
        logger.info("[history] History reset for %s", chat_id)
    except Exception as exc:
        logger.error("[history] Failed to reset history for %s: %s", chat_id, exc)
        await notify_error(exc, context=f"_maybe_compress_history | chat_id={chat_id}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message on /start."""
    if not update.message or not update.effective_chat:
        return
    user = update.effective_user
    await update.message.reply_text(
        f"Hello{', ' + user.first_name if user else ''}!\n"
        "I'm the VIVENTI assistant. How can I help you today?",
        do_quote=True,
    )


async def _handle_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/restart clears the conversation history and resets state to PHASE_1."""
    if not update.message or not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    await services.reset_chat(chat_id)

    from chatbot.domain.conversation_states import ConversationState
    from chatbot.services.conversation_state_service import conversation_state_service

    await services.update_conversation_state(chat_id, ConversationState.PHASE_1)
    conversation_state_service.invalidate_cache(chat_id)

    await update.message.reply_text(
        "Chat restarted. How can I help you?", do_quote=True
    )
    logger.info("'/restart' requested by telegram_id=%s", chat_id)


async def _handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancelar — no active operation to cancel."""
    if not update.message:
        return
    await update.message.reply_text(
        "There is nothing to cancel right now.",
        do_quote=True,
    )


async def _handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download and store the received image in static/images."""
    if not update.message or not update.message.photo or not update.effective_chat:
        return

    chat_id: str = str(update.effective_chat.id)

    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()

        ext: str = ".jpg"
        if tg_file.file_path:
            suffix = tg_file.file_path.rsplit(".", 1)[-1].lower()
            if suffix in {"jpg", "jpeg", "png", "webp"}:
                ext = f".{suffix}"

        images_dir = create_or_retrieve_images_dir()
        file_path = images_dir / f"{chat_id}{ext}"
        await tg_file.download_to_drive(str(file_path))
        logger.info("[image] Saved Telegram image to %s", file_path)

        await update.message.reply_text(
            "File processing is not available at the moment. "
            "Please describe what you need in a text message.",
            do_quote=True,
        )

    except Exception as exc:
        logger.exception("Error saving image for telegram_id=%s: %s", chat_id, exc)
        await notify_error(
            exc,
            context=f"telegram_bot._handle_image | chat_id={chat_id}",
        )


async def _handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download and store the received PDF document in static/documents."""
    if not update.message or not update.message.document or not update.effective_chat:
        return

    chat_id: str = str(update.effective_chat.id)
    doc = update.message.document

    try:
        tg_file = await doc.get_file()
        documents_dir = create_or_retrieve_documents_dir()
        original_name: str = doc.file_name or f"{chat_id}"
        file_path = documents_dir / f"{chat_id}_{original_name}"
        await tg_file.download_to_drive(str(file_path))
        logger.info("[document] Saved Telegram document to %s", file_path)

        await update.message.reply_text(
            "File processing is not available at the moment. "
            "Please describe what you need in a text message.",
            do_quote=True,
        )

    except Exception as exc:
        logger.exception("Error saving document for telegram_id=%s: %s", chat_id, exc)
        await notify_error(
            exc,
            context=f"telegram_bot._handle_document | chat_id={chat_id}",
        )


async def _run_agent_and_reply(
    chat_id: str,
    chat_id_int: int,
    incoming_msg: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Run the AI agent for a given message and send the response."""
    if not update.message:
        return
    logger.info("=" * 80)
    logger.info("telegram_id=%s: %s", chat_id, incoming_msg)

    typing_task = asyncio.create_task(_typing_loop(context.bot, chat_id_int))

    try:
        await services.ensure_system_message(
            phone=chat_id,
            message=CHANNEL_MARKERS[CHANNEL_TELEGRAM],
        )
        await message_handler.save_user_msg(chat_id, incoming_msg)
        await pre_agent_processing(chat_id)

        async def _send_photo_tg(image_bytes: bytes, caption: str) -> None:
            if update.message is None:
                return
            await update.message.reply_photo(
                photo=image_bytes, caption=caption, do_quote=True
            )

        deps = AgentDeps(
            db_services=services,
            whatsapp_client=_noop_whatsapp,
            user_phone=chat_id,
            telegram_id=chat_id,
            send_photo_callback=_send_photo_tg,
        )

        agent = get_viventi_agent()
        history = await services.get_pydantic_ai_history(chat_id, hours=24)
        try:
            try:
                result = await agent.run(
                    incoming_msg, deps=deps, message_history=history
                )
            except ModelHTTPError as http_exc:
                if http_exc.status_code == 503:
                    logger.warning(
                        "[fallback] 503 on primary model for telegram_id=%s — switching to %s",
                        chat_id,
                        FALLBACK_MODEL,
                    )
                    result = await agent.run(
                        incoming_msg,
                        deps=deps,
                        message_history=history,
                        model=FALLBACK_MODEL,
                    )
                else:
                    raise
            ai_response: str = strip_markdown(result.output)
            tools_used = _extract_tools_used(result)
        except UsageLimitExceeded as ule:
            logger.warning(
                "UsageLimitExceeded for telegram_id=%s: %s. Resetting history and retrying...",
                chat_id,
                ule,
            )
            await notify_error(
                ule,
                context=f"_run_agent_and_reply | user={chat_id} | msg={incoming_msg[:200]} | action=reset_retry",
            )
            await services.reset_chat(chat_id)
            logger.info(
                "[history] History reset for %s after UsageLimitExceeded", chat_id
            )
            new_history = await services.get_pydantic_ai_history(chat_id, hours=24)
            try:
                result = await agent.run(
                    incoming_msg, deps=deps, message_history=new_history
                )
                ai_response = strip_markdown(result.output)
                tools_used = _extract_tools_used(result)
            except Exception as retry_exc:
                logger.error(
                    "Retry after reset failed for %s: %s",
                    chat_id,
                    retry_exc,
                    exc_info=True,
                )
                await notify_error(
                    retry_exc,
                    context=f"_run_agent_and_reply | user={chat_id} | msg={incoming_msg[:200]} | action=retry_failed",
                )
                try:
                    explanation = await run_error_agent(str(retry_exc))
                    ai_response = explanation.user_message
                except Exception as explainer_exc:
                    logger.error("Error agent also failed: %s", explainer_exc)
                    ai_response = (
                        "An error occurred while processing your message. "
                        "Please try again or type /restart."
                    )
                tools_used = []
        except Exception as agent_exc:
            logger.error(
                "Agent error for telegram_id=%s: %s",
                chat_id,
                agent_exc,
                exc_info=True,
            )
            await notify_error(
                agent_exc,
                context=f"_run_agent_and_reply | user={chat_id} | msg={incoming_msg[:200]}",
            )
            try:
                explanation = await run_error_agent(str(agent_exc))
                ai_response = explanation.user_message
            except Exception as explainer_exc:
                logger.error("Error agent also failed: %s", explainer_exc)
                ai_response = (
                    "An error occurred while processing your message. "
                    "Please try again or type /restart."
                )
            tools_used = []

        logger.info("Agent response for telegram_id=%s: %s", chat_id, ai_response)
        logger.debug("Tools used: %s", tools_used)

        await message_handler.save_assistant_msg(chat_id, ai_response, tools_used)
        await update.message.reply_text(ai_response, do_quote=True)
        asyncio.create_task(_maybe_compress_history(chat_id, len(history)))

    finally:
        typing_task.cancel()


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process an incoming text message through the AI agent."""
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id_int: int = update.effective_chat.id
    chat_id: str = str(chat_id_int)
    incoming_msg: str = update.message.text

    try:
        await _run_agent_and_reply(chat_id, chat_id_int, incoming_msg, update, context)

    except Exception as exc:
        logger.exception(
            "Error processing message for telegram_id=%s: %s", chat_id, exc
        )
        await notify_error(
            exc,
            context=f"_handle_message | chat_id={chat_id} | msg={incoming_msg[:200]}",
        )
        if update.message:
            await update.message.reply_text(
                "An error occurred while processing your message. "
                "Please try again or type /restart.",
                do_quote=True,
            )


async def _handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Transcribe a Telegram voice note and process it as a text message."""
    if not update.message or not update.message.voice or not update.effective_chat:
        return

    chat_id_int: int = update.effective_chat.id
    chat_id: str = str(chat_id_int)

    try:
        tg_file = await update.message.voice.get_file()
        voice_dir = create_or_retrieve_voice_dir()
        file_path = voice_dir / f"{chat_id}.oga"
        await tg_file.download_to_drive(str(file_path))
        logger.info("[voice] Saved Telegram voice note to %s", file_path)

        try:
            if config.USE_FFMPEG and ".oga" not in AVAILABLE_AUDIO_FORMATS:
                mp3_path = file_path.with_suffix(".mp3")
                ok = await convert_ogg_to_mp3(
                    input_path=file_path, output_path=mp3_path
                )
                if ok:
                    try:
                        transcription = await transcribe_audio(str(mp3_path))
                    finally:
                        file_path.unlink(missing_ok=True)
                        mp3_path.unlink(missing_ok=True)
                else:
                    try:
                        transcription = await transcribe_audio(str(file_path))
                    finally:
                        file_path.unlink(missing_ok=True)
            else:
                try:
                    transcription = await transcribe_audio(str(file_path))
                finally:
                    file_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.exception(
                "[voice] Transcription failed for telegram_id=%s: %s", chat_id, exc
            )
            await update.message.reply_text(
                "I couldn't process your voice note. Please try again or type your message.",
                do_quote=True,
            )
            return

        logger.info(
            "[voice] Transcription for telegram_id=%s: %s", chat_id, transcription
        )
        await _run_agent_and_reply(chat_id, chat_id_int, transcription, update, context)

    except Exception as exc:
        logger.exception(
            "Error processing voice note for telegram_id=%s: %s", chat_id, exc
        )
        await notify_error(
            exc,
            context=f"telegram_bot._handle_voice | chat_id={chat_id}",
        )
        if update.message:
            await update.message.reply_text(
                "An error occurred while processing your voice note. "
                "Please try again or type /restart.",
                do_quote=True,
            )


# ---------------------------------------------------------------------------
# Bot lifecycle
# ---------------------------------------------------------------------------


async def _post_init(application: Application) -> None:
    """Connect to DB on startup."""
    init_logging()
    logger.info("VIVENTI Bot starting up")
    await services.database.connect()
    logger.info("DB connected")


async def _post_shutdown(application: Application) -> None:
    """Disconnect DB on shutdown."""
    try:
        await services.database.disconnect()
        logger.info("DB disconnected")
    except Exception as exc:
        logger.error("Error disconnecting DB: %s", exc)


def build_application() -> Application:
    """Build and return the configured PTB Application."""
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured in .env")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", _handle_start))
    app.add_handler(CommandHandler("restart", _handle_restart))
    app.add_handler(CommandHandler("cancelar", _handle_cancel))
    app.add_handler(CommandHandler("cancel", _handle_cancel))
    app.add_handler(
        CommandHandler("test_dev_notifications", cmd_test_dev_notifications)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, _handle_image))
    app.add_handler(MessageHandler(filters.Document.ALL, _handle_document))

    return app

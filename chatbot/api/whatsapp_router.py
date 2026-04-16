import asyncio
import logging
import time
import traceback
from datetime import datetime

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic_ai import AgentRunResult
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart

from chatbot.ai_agent import get_viventi_agent
from chatbot.ai_agent.agent import FALLBACK_MODEL
from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.ai_agent.error_agent import run_error_agent
from chatbot.api.utils import message_handler
from chatbot.api.utils.message_queue import Message, message_queue
from chatbot.api.utils.text import strip_markdown
from chatbot.api.utils.webhook_parser import extract_message_content
from chatbot.core.config import config
from chatbot.db.services import services
from chatbot.messaging.telegram_notifier import notify_error, notify_slow_response
from chatbot.messaging.whatsapp import whatsapp_manager

logger = logging.getLogger(__name__)
load_dotenv()
router = APIRouter()
ERROR_STATUS = {"status": "error"}
OK_STATUS = {"status": "ok"}
USER_ERROR_MSG = "An error occurred while processing your message. Please try again or send /restart to restart the chat."

CHANNEL_WHATSAPP: str = "whatsapp"
CHANNEL_TELEGRAM: str = "telegram"
CHANNEL_MARKERS: dict[str, str] = {
    CHANNEL_WHATSAPP: "CHANNEL: whatsapp",
    CHANNEL_TELEGRAM: "CHANNEL: telegram",
}

# Excepciones que indican un fallo transitorio del proveedor de IA y ameritan reintento
_PROVIDER_ERRORS = (ModelAPIError, httpx.TimeoutException, httpx.ConnectError)

SLOW_RESPONSE_THRESHOLD: float = 30.0
HISTORY_SUMMARY_THRESHOLD: int = 30


async def _maybe_compress_history(user_number: str, history_len: int) -> None:
    """Resetea el historial si tras el turno actual supera el umbral."""
    total = history_len + 2  # +1 usuario + 1 asistente del turno actual
    if total <= HISTORY_SUMMARY_THRESHOLD:
        return

    logger.info(
        "[history] Resetting history for %s (%d messages > %d threshold)",
        user_number,
        total,
        HISTORY_SUMMARY_THRESHOLD,
    )
    try:
        await services.reset_chat(user_number)
        logger.info("[history] History reset for %s", user_number)
    except Exception as exc:
        logger.error("[history] Failed to reset history for %s: %s", user_number, exc)
        await notify_error(exc, context=f"_maybe_compress_history | user={user_number}")


@router.get("")
async def verify_webhook(request: Request):
    try:
        mode = request.query_params.get("hub.mode")
        challenge = request.query_params.get("hub.challenge")
        token = request.query_params.get("hub.verify_token")

        verify_token_expected = config.WHATSAPP_VERIFY_TOKEN

        if mode == "subscribe" and token == verify_token_expected:
            logger.info("WEBHOOK VERIFIED for Meta WhatsApp API")
            return PlainTextResponse(str(challenge))
        else:
            logger.warning(
                f"Webhook verification failed - Mode: {mode}, "
                f"Token match: {token == verify_token_expected}"
            )
            raise HTTPException(status_code=403, detail="Forbidden")
    except Exception as e:
        logger.error(f"Error in webhook verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


def _extract_tools_used(result: AgentRunResult[str]) -> list[str]:
    """Extract tool names called during the agent run."""
    tools: list[str] = []
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    tools.append(part.tool_name)
    return tools


async def _process_message(message: Message) -> None:
    """Process a single message from the queue sequentially per user."""
    user_number = message.user_number
    incoming_msg = message.content
    message_id = message.message_id

    if not message_id:
        logger.error("No message_id provided for WhatsApp message")
        return

    await whatsapp_manager.mark_read(message_id)
    await whatsapp_manager.send_typing_indicator(message_id)

    try:
        if incoming_msg.lower() == "/restart":
            logger.info("'/restart' requested by %s", user_number)
            await services.reset_chat(user_number)
            await whatsapp_manager.send_text(
                user_number=user_number, text="Chat restarted", message_id=message_id
            )
            return

        logger.info("=" * 80)
        logger.info("%s: %s", user_number, incoming_msg)

        await services.ensure_system_message(
            phone=user_number,
            message=CHANNEL_MARKERS[CHANNEL_WHATSAPP],
        )
        await message_handler.save_user_msg(user_number, incoming_msg)

        async def _send_photo_wa(image_bytes: bytes, caption: str) -> None:
            media_id = await whatsapp_manager.upload_media_bytes(image_bytes)
            await whatsapp_manager.send_image_by_id(
                to=user_number, image_id=media_id, caption=caption
            )

        deps = AgentDeps(
            db_services=services,
            whatsapp_client=whatsapp_manager,
            user_phone=user_number,
            send_photo_callback=_send_photo_wa,
        )

        agent = get_viventi_agent()
        history = await services.get_pydantic_ai_history(user_number, hours=24)

        ai_response: str
        tools_used: list[str]
        message_datetime = datetime.now()
        provider_error: str | None = None

        try:
            agent_start = time.monotonic()
            try:
                result = await agent.run(
                    incoming_msg, deps=deps, message_history=history
                )
            except _PROVIDER_ERRORS as provider_exc:
                logger.warning(
                    "Provider error on first attempt for %s: %s. Retrying...",
                    user_number,
                    provider_exc,
                )
                provider_error = f"{type(provider_exc).__name__}: {provider_exc}"
                if (
                    isinstance(provider_exc, ModelHTTPError)
                    and provider_exc.status_code == 503
                ):
                    logger.info(
                        "[fallback] 503 on primary model — switching to %s",
                        FALLBACK_MODEL,
                    )
                    result = await agent.run(
                        incoming_msg,
                        deps=deps,
                        message_history=history,
                        model=FALLBACK_MODEL,
                    )
                else:
                    result = await agent.run(
                        incoming_msg, deps=deps, message_history=history
                    )
            except UsageLimitExceeded as ule:
                logger.warning(
                    "UsageLimitExceeded for %s: %s. Resetting history and retrying...",
                    user_number,
                    ule,
                )
                await notify_error(
                    ule,
                    context=f"_process_message | user={user_number} | msg={incoming_msg[:200]} | action=reset_retry",
                )
                await services.reset_chat(user_number)
                logger.info(
                    "[history] History reset for %s after UsageLimitExceeded",
                    user_number,
                )
                new_history = await services.get_pydantic_ai_history(
                    user_number, hours=24
                )
                result = await agent.run(
                    incoming_msg, deps=deps, message_history=new_history
                )

            response_time = time.monotonic() - agent_start
            ai_response = strip_markdown(result.output)
            tools_used = _extract_tools_used(result)

            if response_time > SLOW_RESPONSE_THRESHOLD:
                logger.warning(
                    "Slow response for %s: %.1fs", user_number, response_time
                )
                await notify_slow_response(
                    phone=user_number,
                    user_message=incoming_msg,
                    tools_used=tools_used,
                    ai_response=ai_response,
                    message_datetime=message_datetime,
                    history_count=len(history),
                    response_time=response_time,
                    provider_error=provider_error,
                )

        except Exception as agent_exc:
            logger.error(
                "Agent error for %s: %s", user_number, agent_exc, exc_info=True
            )
            await notify_error(
                agent_exc,
                context=f"_process_message | user={user_number} | msg={incoming_msg[:200]}",
            )
            try:
                explanation = await run_error_agent(traceback.format_exc())
                ai_response = explanation.user_message
            except Exception as explainer_exc:
                logger.error("Error agent also failed: %s", explainer_exc)
                ai_response = USER_ERROR_MSG
            tools_used = []

        logger.info("Agent response for %s: %s", user_number, ai_response)
        logger.info("Tools used: %s", tools_used)

        await message_handler.save_assistant_msg(user_number, ai_response, tools_used)
        await whatsapp_manager.send_text(
            user_number=user_number, text=ai_response, message_id=message_id
        )
        asyncio.create_task(_maybe_compress_history(user_number, len(history)))

    except Exception as exc:
        logger.exception("Error processing message for %s: %s", user_number, exc)
        await notify_error(
            exc,
            context=f"_process_message | user={user_number} | msg={incoming_msg[:200]}",
        )
        await whatsapp_manager.send_text(
            user_number=user_number, text=USER_ERROR_MSG, message_id=message_id
        )


@router.post("")
async def whatsapp_reply(request: Request):
    logger.info("Received WhatsApp message webhook")
    try:
        webhook_data = await request.json()
    except Exception as exc:
        logger.error(f"Error parsing webhook data: {exc}")
        return ERROR_STATUS

    message_data = await extract_message_content(webhook_data)
    if not message_data:
        return OK_STATUS

    user_number = message_data.user_number
    message_id = message_data.message_id

    # --- Unsupported document format ---
    if message_data.unsupported_format:
        await whatsapp_manager.mark_read(message_id)
        await whatsapp_manager.send_text(
            user_number=user_number,
            text=(
                "The file format is not supported. "
                "Please send your file as a JPG, PNG or PDF."
            ),
            message_id=message_id,
        )
        return OK_STATUS

    # --- Image/PDF: file already stored in filesystem, nothing else to do ---
    if message_data.media_file_path is not None:
        await whatsapp_manager.mark_read(message_id)
        logger.info(
            "[media] File stored for user=%s path=%s",
            user_number,
            message_data.media_file_path,
        )
        return OK_STATUS

    # --- Text / audio: queue for agent processing ---
    incoming_msg = message_data.text or ""
    if not incoming_msg:
        return OK_STATUS

    msg = Message(user_number=user_number, content=incoming_msg, message_id=message_id)
    await message_queue.enqueue(msg)
    await message_queue.start_processing(user_number, _process_message)

    queue_size = message_queue.queue_size(user_number)
    if queue_size > 1:
        logger.warning(f"Queue size for {user_number} is {queue_size}")

    return OK_STATUS

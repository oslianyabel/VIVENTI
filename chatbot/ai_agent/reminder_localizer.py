"""Reminder localizer sub-agent.

Receives the user's conversation history and a notification message in Spanish,
then returns the notification translated/adapted to the user's language.
"""

from __future__ import annotations

import logging

import httpx
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel as PydanticAIGoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.settings import ModelSettings

from chatbot.ai_agent.models import GoogleModel

logger = logging.getLogger(__name__)

_LOCALIZER_SYSTEM_PROMPT: str = """\
Eres un asistente especializado en localizar mensajes de notificación.

Recibirás:
1. El historial reciente de una conversación con un cliente.
2. Un mensaje de notificación en español.

Tu tarea:
- Detecta el idioma que usa el cliente en sus mensajes.
- Si el cliente escribe en español (cualquier variante), devuelve el mensaje \
  con variación natural (no una copia textual, pero mantené el significado).
- Si el cliente escribe en portugués, traducí al portugués brasileño.
- Si el cliente escribe en inglés, traducí al inglés.
- Para cualquier otro idioma, traducí al idioma detectado.
- Mantené un tono cálido, profesional y breve.
- No agregues información que no esté en el mensaje original.
- Devolvé SOLO el mensaje localizado, sin explicación adicional.
"""


async def localize_notification(
    conversation_history: list[str],
    notification_text: str,
) -> str:
    """Localize a notification message to the user's language.

    Args:
        conversation_history: Recent conversation messages for language detection.
        notification_text: The notification content in Spanish.

    Returns:
        The notification adapted to the user's language.
    """
    logger.info("[reminder_localizer] Localizing notification")

    history_str = "\n".join(conversation_history[-15:])
    user_prompt = (
        f"## Historial de la conversación:\n{history_str}\n\n"
        f"## Mensaje a localizar:\n{notification_text}"
    )

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        provider = GoogleProvider(http_client=http_client)
        model_name = GoogleModel.Gemini_Flash_Latest.value.split(":", 1)[-1]
        google_model = PydanticAIGoogleModel(model_name, provider=provider)

        agent: Agent[None, str] = Agent(
            model=google_model,
            system_prompt=_LOCALIZER_SYSTEM_PROMPT,
            output_type=str,
            model_settings=ModelSettings(temperature=0.3),
        )
        result = await agent.run(user_prompt)
        del agent

    localized = result.output
    logger.info("[reminder_localizer] Result: %s", localized[:100])
    return localized

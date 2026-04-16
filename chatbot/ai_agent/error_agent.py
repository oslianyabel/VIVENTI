"""Error-explainer sub-agent for the Telegram bot.

Receives a raw exception traceback/message from the main cheese agent and
returns a user-friendly explanation that identifies the tool that failed
and offers actionable suggestions.

Usage::

    explanation = await run_error_agent(str(exc))
    await update.message.reply_text(explanation.user_message)
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel as PydanticAIGoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.settings import ModelSettings

from chatbot.ai_agent.models import GoogleModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class ErrorExplanation(BaseModel):
    """User-facing explanation produced by the error-explainer sub-agent."""

    tool_name: str
    """Name of the agent tool that caused the error (or 'unknown')."""

    user_message: str
    """Friendly message for the end user explaining what happened and what to do."""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_ERROR_SYSTEM_PROMPT: str = """\
Eres un asistente especializado en interpretar errores técnicos del sistema \
"Viventi" y traducirlos a mensajes comprensibles para el usuario final.

Las herramientas disponibles en el sistema son:
- resolve_relative_date: convierte expresiones de fecha relativas a fechas absolutas
- phase_1_to_phase_2: transición de estado PHASE_1 -> PHASE_2
- phase_3_to_completed: transición de estado PHASE_3 -> COMPLETED
- lost_to_completed: transición de estado LOST -> COMPLETED
- get_available_slots: consulta disponibilidad en Google Calendar
- get_google_sheets_data: recupera filas de Google Sheets
- update_user_data: guarda un dato personal del usuario
- save_phase_2_answers: guarda respuestas de calificación PHASE_2
- evaluate_and_transition_phase_2: evalúa calificación y ejecuta transición
- create_google_calendar_event: crea evento de demo en Google Calendar
- update_google_calendar_event: reagenda demo
- cancel_google_calendar_event: cancela demo
- add_google_sheets_data: sincroniza datos con Google Sheets

TAREA
1. Analiza el error recibido e identifica la herramienta que lo causó.
2. Produce:
   - tool_name: nombre exacto de la herramienta causante (o "unknown" si no se puede determinar)
   - user_message: mensaje en español, claro, sin tecnicismos, que:
       a) Indique al usuario cuál operación falló (sin mencionar nombres de código)
       b) Explique brevemente por qué pudo ocurrir
       c) Ofrezca 1-2 sugerencias concretas para solucionarlo o evitarlo

El mensaje debe ser cordial y empático. Máximo 4 oraciones.
"""

# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


async def run_error_agent(raw_error: str) -> ErrorExplanation:
    """Interpret a raw agent exception and return a user-friendly explanation.

    Args:
        raw_error: The string representation of the exception raised by the
                   main cheese agent (str(exc) or full traceback).

    Returns:
        ErrorExplanation with tool_name and a user-friendly message.
    """
    logger.info("[run_error_agent] analyzing error: %s", raw_error[:200])

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        provider = GoogleProvider(http_client=http_client)
        model_name = GoogleModel.Gemini_Flash_Lite_Latest.value.split(":", 1)[-1]
        google_model = PydanticAIGoogleModel(model_name, provider=provider)

        agent: Agent[None, ErrorExplanation] = Agent(
            model=google_model,
            system_prompt=_ERROR_SYSTEM_PROMPT,
            output_type=ErrorExplanation,
            model_settings=ModelSettings(temperature=0),
        )
        result = await agent.run(f"Error recibido:\n{raw_error}")
        del agent

    explanation = result.output
    logger.info(
        "[run_error_agent] tool=%s | message=%s",
        explanation.tool_name,
        explanation.user_message[:100],
    )
    return explanation

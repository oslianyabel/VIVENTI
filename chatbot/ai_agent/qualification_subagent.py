"""Qualification classifier sub-agent.

Receives PHASE_2 answers and conversation context, returns a structured
QualificationResult indicating whether the lead qualifies for PHASE_3.
Pure text-in → structured-out classification — no tools, no user-facing text.
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
from chatbot.domain.qualification import DisqualificationReason

logger = logging.getLogger(__name__)


class QualificationResult(BaseModel):
    """Structured output from the qualification classifier."""

    qualifies: bool
    disqualification_reason: DisqualificationReason | None = None
    experience_type: str | None = None
    country: str | None = None
    reservation_method: str | None = None
    monthly_reservations: int | None = None
    payment_method: str | None = None
    has_instagram: bool | None = None
    uses_instagram_for_sales: bool | None = None
    main_pain_point: str | None = None
    notes: str | None = None


_QUALIFICATION_SYSTEM_PROMPT: str = """\
Eres un clasificador de leads para Viventi, una plataforma de reservas para \
operadores de turismo experiencial en LATAM.

Tu tarea es analizar las respuestas a 6 preguntas de calificación y determinar \
si el lead califica para una demo.

## CRITERIOS DE CALIFICACIÓN

CALIFICA si cumple TODAS estas condiciones:
1. Tipo de experiencia: bodega, glamping, hacienda café/cacao, circuito gastronómico, \
   tour guiado, picantería, turismo rural/vivencial, o similar.
2. País: cualquier país de LATAM.
3. Gestión actual: manual (WhatsApp, teléfono, correo, planilla).
4. Señal de presupuesto — al menos UNA de estas:
   a) Más de 5 reservas por mes.
   b) Cobra más de USD 30 por persona (infiere esto del tipo de experiencia, \
      país y volumen — NO se pregunta directamente).
   c) Tiene Instagram activo con seguidores o consultas frecuentes.

NO CALIFICA si cumple ALGUNA de estas exclusiones:
- Es hotel de cadena integrado en Booking/Expedia como canal principal.
- Es turista o agencia que vende paquetes de terceros.
- Volumen casi nulo (1-2 reservas/mes) Y precio muy bajo (<USD 15/persona) \
  Y sin Instagram. No tiene presupuesto real.

## INSTRUCCIONES DE INFERENCIA

- experience_type: normaliza la respuesta a una categoría corta.
- country: normaliza al nombre del país.
- reservation_method: normaliza a whatsapp/telefono/correo/planilla/otro.
- monthly_reservations: extrae el número estimado. Si dice "pocas" = 3, \
  "bastantes" = 15, "muchas" = 30.
- payment_method: normaliza a transferencia/efectivo/tarjeta/mercadopago/otro.
- has_instagram / uses_instagram_for_sales: booleanos inferidos de la respuesta 6.
- main_pain_point: infiere el principal dolor del operador a partir del contexto \
  completo (cómo gestiona reservas, problemas mencionados, etc.).
- disqualification_reason: si no califica, indica la razón principal usando \
  exactamente uno de: hotel_chain, tourist, agency, low_volume, other.
- notes: observaciones adicionales relevantes para el equipo comercial.

Responde SOLO con el JSON estructurado. No incluyas texto adicional.
"""


async def run_qualification_subagent(
    answers_text: str,
    conversation_context: list[str] | None = None,
) -> QualificationResult:
    """Run the qualification classifier on the provided answers.

    Args:
        answers_text: Formatted string with the 6 questions and answers.
        conversation_context: Optional list of recent conversation messages
            for additional context.

    Returns:
        QualificationResult with classification decision and inferred fields.
    """
    logger.info("[qualification_subagent] Starting classification")

    prompt_parts: list[str] = [answers_text]
    if conversation_context:
        context_str = "\n".join(conversation_context[-20:])
        prompt_parts.append(
            f"\n## Contexto adicional de la conversación:\n{context_str}"
        )

    user_prompt = "\n".join(prompt_parts)

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        provider = GoogleProvider(http_client=http_client)
        model_name = GoogleModel.Gemini_Flash_Latest.value.split(":", 1)[-1]
        google_model = PydanticAIGoogleModel(model_name, provider=provider)

        agent: Agent[None, QualificationResult] = Agent(
            model=google_model,
            system_prompt=_QUALIFICATION_SYSTEM_PROMPT,
            output_type=QualificationResult,
            model_settings=ModelSettings(temperature=0),
        )
        result = await agent.run(user_prompt)
        del agent

    output = result.output
    logger.info(
        "[qualification_subagent] qualifies=%s reason=%s exp_type=%s country=%s",
        output.qualifies,
        output.disqualification_reason,
        output.experience_type,
        output.country,
    )
    return output

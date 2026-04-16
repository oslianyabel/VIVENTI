"""Stateless qualification evaluation service.

Builds the prompt payload from answers and optional context, calls the
qualification subagent, and returns the result without side effects.
"""

from __future__ import annotations

import logging

from chatbot.ai_agent.qualification_subagent import (
    QualificationResult,
    run_qualification_subagent,
)
from chatbot.domain.qualification import QualificationAnswers

logger = logging.getLogger(__name__)

_QUESTIONS: list[str] = [
    "¿Qué tipo de experiencia ofrecés?",
    "¿En qué país o región estás?",
    "¿Cómo recibís reservas hoy?",
    "¿Cuántas reservas recibís por mes, más o menos?",
    "¿Cómo cobrás las reservas?",
    "¿Tenés Instagram o Facebook para tu experiencia? ¿Lo usás para conseguir reservas?",
]


def _build_answers_text(answers: QualificationAnswers) -> str:
    """Format the 6 questions + answers into a readable prompt block."""
    raw = answers.as_dict()
    lines: list[str] = ["## Respuestas de calificación (PHASE_2)\n"]
    for i, question in enumerate(_QUESTIONS, start=1):
        key = f"phase_2_answer_{i}"
        answer = raw.get(key) or "(sin respuesta)"
        lines.append(f"**Pregunta {i}:** {question}")
        lines.append(f"**Respuesta:** {answer}\n")
    return "\n".join(lines)


async def evaluate_qualification(
    answers: QualificationAnswers,
    conversation_context: list[str] | None = None,
) -> QualificationResult:
    """Evaluate whether a lead qualifies for PHASE_3.

    Args:
        answers: The 6 PHASE_2 answers collected from the user.
        conversation_context: Optional recent conversation messages for
            disambiguation and pain-point inference.

    Returns:
        QualificationResult with the classification decision.
    """
    logger.info("[qualification_service] Evaluating qualification")
    answers_text = _build_answers_text(answers)
    result = await run_qualification_subagent(answers_text, conversation_context)
    logger.info("[qualification_service] Result: qualifies=%s", result.qualifies)
    return result

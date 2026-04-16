"""Qualification and PHASE_2 evaluation tools for the VIVENTI agent."""

from __future__ import annotations

import logging

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from chatbot.ai_agent.dependencies import AgentDeps

logger = logging.getLogger(__name__)


async def save_phase_2_answers(
    ctx: RunContext[AgentDeps],
    answer_1: str | None = None,
    answer_2: str | None = None,
    answer_3: str | None = None,
    answer_4: str | None = None,
    answer_5: str | None = None,
    answer_6: str | None = None,
) -> str:
    """Persist PHASE_2 qualification answers to the database.

    Call this tool to save the user's answers to the 6 qualification questions.
    Pass only the answers that are available so far.

    Args:
        ctx: Agent run context (injected automatically).
        answer_1: Answer to Q1 (experience type).
        answer_2: Answer to Q2 (country/region).
        answer_3: Answer to Q3 (current reservation method).
        answer_4: Answer to Q4 (monthly reservations).
        answer_5: Answer to Q5 (payment method).
        answer_6: Answer to Q6 (Instagram usage).

    Returns:
        Confirmation of the save.
    """
    logger.info("[save_phase_2_answers] phone=%s", ctx.deps.user_phone)
    from chatbot.db.services import services

    answers: dict[str, str | None] = {}
    if answer_1 is not None:
        answers["phase_2_answer_1"] = answer_1
    if answer_2 is not None:
        answers["phase_2_answer_2"] = answer_2
    if answer_3 is not None:
        answers["phase_2_answer_3"] = answer_3
    if answer_4 is not None:
        answers["phase_2_answer_4"] = answer_4
    if answer_5 is not None:
        answers["phase_2_answer_5"] = answer_5
    if answer_6 is not None:
        answers["phase_2_answer_6"] = answer_6

    if answers:
        await services.update_phase_2_answers(ctx.deps.user_phone, answers)
    return f"Respuestas guardadas: {list(answers.keys())}"


async def evaluate_and_transition_phase_2(
    ctx: RunContext[AgentDeps],
) -> str:
    """Evaluate PHASE_2 qualification and execute the appropriate transition.

    Call this tool ONLY after all 6 PHASE_2 questions have been answered.
    Internally calls the qualification subagent to classify the lead and
    transitions to PHASE_3 (qualified) or DISCARD (not qualified).

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Qualification outcome: qualified (move to PHASE_3) or disqualified
        (move to DISCARD) with the reason.
    """
    logger.info("[evaluate_and_transition_phase_2] phone=%s", ctx.deps.user_phone)
    from chatbot.db.services import services
    from chatbot.domain.conversation_states import ConversationState
    from chatbot.domain.qualification import QualificationAnswers
    from chatbot.services.conversation_state_service import conversation_state_service
    from chatbot.services.lead_orchestrator import orchestrate_after_phase_2

    state = await conversation_state_service.get_state(ctx.deps.user_phone)
    if state != ConversationState.PHASE_2:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en PHASE_2. "
            "Primero usa phase_1_to_phase_2 para avanzar a PHASE_2."
        )

    user = await services.get_user(ctx.deps.user_phone)
    if not user:
        raise ModelRetry("No se encontró el usuario en la base de datos.")

    answers = QualificationAnswers(
        phase_2_answer_1=getattr(user, "phase_2_answer_1", None),
        phase_2_answer_2=getattr(user, "phase_2_answer_2", None),
        phase_2_answer_3=getattr(user, "phase_2_answer_3", None),
        phase_2_answer_4=getattr(user, "phase_2_answer_4", None),
        phase_2_answer_5=getattr(user, "phase_2_answer_5", None),
        phase_2_answer_6=getattr(user, "phase_2_answer_6", None),
    )

    messages = await services.get_recent_messages(ctx.deps.user_phone, hours=24)
    context: list[str] = [f"{msg.role}: {msg.message}" for msg in messages]

    result = await orchestrate_after_phase_2(
        phone=ctx.deps.user_phone,
        answers=answers,
        context_messages=context,
    )

    if result.qualifies:
        return (
            "El lead CALIFICA. Estado actualizado a PHASE_3. "
            "Proponé la demo de 30 minutos al usuario."
        )
    reason = result.disqualification_reason or "otro"
    return (
        f"El lead NO califica (razón: {reason}). Estado actualizado a DISCARD. "
        "Enviá un mensaje de cierre amable."
    )


async def re_evaluate_discard_answers(
    ctx: RunContext[AgentDeps],
) -> str:
    """Re-evaluate a DISCARD user after their answers have been updated.

    Call this tool ONLY when the user is in DISCARD state and has provided
    a new or corrected answer that was already saved with save_phase_2_answers.
    Reads the updated answers from the database and runs the qualification
    subagent again. If qualified, transitions to PHASE_3.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Re-evaluation outcome: qualified (PHASE_3) or still disqualified.
    """
    logger.info("[re_evaluate_discard_answers] phone=%s", ctx.deps.user_phone)
    from chatbot.db.services import services
    from chatbot.domain.conversation_states import ConversationState
    from chatbot.services.conversation_state_service import conversation_state_service
    from chatbot.services.lead_orchestrator import re_evaluate_discard

    state = await conversation_state_service.get_state(ctx.deps.user_phone)
    if state != ConversationState.DISCARD:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en DISCARD. "
            "Esta herramienta solo aplica cuando el estado es DISCARD."
        )

    messages = await services.get_recent_messages(ctx.deps.user_phone, hours=72)
    context: list[str] = [f"{msg.role}: {msg.message}" for msg in messages]

    result = await re_evaluate_discard(ctx.deps.user_phone, context)

    if result.qualifies:
        return (
            "El lead ahora CALIFICA. Estado actualizado a PHASE_3. "
            "Proponé la demo de 30 minutos al usuario."
        )
    reason = result.disqualification_reason or "otro"
    return f"El lead sigue sin calificar (razón: {reason}). Mantener en DISCARD."

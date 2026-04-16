"""State transition tools for the VIVENTI agent."""

from __future__ import annotations

import logging

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.domain.conversation_states import ConversationState
from chatbot.services.conversation_state_service import (
    InvalidConversationStateTransitionError,
    conversation_state_service,
)

logger = logging.getLogger(__name__)


async def phase_1_to_phase_2(ctx: RunContext[AgentDeps]) -> str:
    """Transition conversation from PHASE_1 to PHASE_2.

    Call this tool when the user confirms they operate a tourism experience.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation of the state transition.
    """
    phone = ctx.deps.user_phone
    logger.info("[phase_1_to_phase_2] phone=%s", phone)

    state = await conversation_state_service.get_state(phone)
    if state != ConversationState.PHASE_1:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en PHASE_1. "
            "Esta herramienta solo aplica cuando el estado es PHASE_1."
        )

    try:
        await conversation_state_service.phase_1_to_phase_2(phone)
    except InvalidConversationStateTransitionError as exc:
        raise ModelRetry(str(exc))
    return "Estado actualizado a PHASE_2."


async def phase_3_to_completed(ctx: RunContext[AgentDeps]) -> str:
    """Transition conversation from PHASE_3 to COMPLETED.

    Call this tool after a demo has been successfully scheduled.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation of the state transition.
    """
    phone = ctx.deps.user_phone
    logger.info("[phase_3_to_completed] phone=%s", phone)

    state = await conversation_state_service.get_state(phone)
    if state != ConversationState.PHASE_3:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en PHASE_3. "
            "Esta herramienta solo aplica cuando el estado es PHASE_3."
        )

    try:
        await conversation_state_service.phase_3_to_completed(phone)
    except InvalidConversationStateTransitionError as exc:
        raise ModelRetry(str(exc))
    return "Estado actualizado a COMPLETED."


async def phase_3_to_lost(ctx: RunContext[AgentDeps]) -> str:
    """Transition conversation from PHASE_3 to LOST.

    Call this tool when the user in PHASE_3 explicitly rejects scheduling a demo.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation of the state transition.
    """
    phone = ctx.deps.user_phone
    logger.info("[phase_3_to_lost] phone=%s", phone)

    state = await conversation_state_service.get_state(phone)
    if state != ConversationState.PHASE_3:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en PHASE_3. "
            "Esta herramienta solo aplica cuando el estado es PHASE_3."
        )

    try:
        await conversation_state_service.phase_3_to_lost(phone)
    except InvalidConversationStateTransitionError as exc:
        raise ModelRetry(str(exc))
    return "Estado actualizado a LOST."


async def lost_to_completed(ctx: RunContext[AgentDeps]) -> str:
    """Transition conversation from LOST to COMPLETED.

    Call this tool when a LOST user re-engages and schedules a demo.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation of the state transition.
    """
    phone = ctx.deps.user_phone
    logger.info("[lost_to_completed] phone=%s", phone)

    state = await conversation_state_service.get_state(phone)
    if state != ConversationState.LOST:
        raise ModelRetry(
            f"La conversación está en {state.value}, no en LOST. "
            "Esta herramienta solo aplica cuando el estado es LOST."
        )

    try:
        await conversation_state_service.lost_to_completed(phone)
    except InvalidConversationStateTransitionError as exc:
        raise ModelRetry(str(exc))
    return "Estado actualizado a COMPLETED."

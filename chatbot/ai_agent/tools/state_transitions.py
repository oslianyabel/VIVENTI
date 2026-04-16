"""State transition tools for the VIVENTI agent."""

from __future__ import annotations

import logging

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from chatbot.ai_agent.dependencies import AgentDeps

logger = logging.getLogger(__name__)


async def phase_1_to_phase_2(ctx: RunContext[AgentDeps]) -> str:
    """Transition conversation from PHASE_1 to PHASE_2.

    Call this tool when the user confirms they operate a tourism experience.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation of the state transition.
    """
    logger.info("[phase_1_to_phase_2] phone=%s", ctx.deps.user_phone)
    from chatbot.services.conversation_state_service import (
        InvalidConversationStateTransitionError,
        conversation_state_service,
    )

    try:
        await conversation_state_service.phase_1_to_phase_2(ctx.deps.user_phone)
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
    logger.info("[phase_3_to_completed] phone=%s", ctx.deps.user_phone)
    from chatbot.services.conversation_state_service import (
        InvalidConversationStateTransitionError,
        conversation_state_service,
    )

    try:
        await conversation_state_service.phase_3_to_completed(ctx.deps.user_phone)
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
    logger.info("[phase_3_to_lost] phone=%s", ctx.deps.user_phone)
    from chatbot.services.conversation_state_service import (
        InvalidConversationStateTransitionError,
        conversation_state_service,
    )

    try:
        await conversation_state_service.phase_3_to_lost(ctx.deps.user_phone)
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
    logger.info("[lost_to_completed] phone=%s", ctx.deps.user_phone)
    from chatbot.services.conversation_state_service import (
        InvalidConversationStateTransitionError,
        conversation_state_service,
    )

    try:
        await conversation_state_service.lost_to_completed(ctx.deps.user_phone)
    except InvalidConversationStateTransitionError as exc:
        raise ModelRetry(str(exc))
    return "Estado actualizado a COMPLETED."

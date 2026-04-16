from __future__ import annotations

from enum import StrEnum


class ConversationState(StrEnum):
    PHASE_1 = "PHASE_1"
    PHASE_2 = "PHASE_2"
    PHASE_3 = "PHASE_3"
    COMPLETED = "COMPLETED"
    DISCARD = "DISCARD"
    LOST = "LOST"


INITIAL_CONVERSATION_STATE: ConversationState = ConversationState.PHASE_1

ALLOWED_STATE_TRANSITIONS: dict[ConversationState, frozenset[ConversationState]] = {
    ConversationState.PHASE_1: frozenset({ConversationState.PHASE_2}),
    ConversationState.PHASE_2: frozenset(
        {ConversationState.PHASE_3, ConversationState.DISCARD}
    ),
    ConversationState.PHASE_3: frozenset(
        {ConversationState.COMPLETED, ConversationState.LOST}
    ),
    ConversationState.COMPLETED: frozenset({ConversationState.LOST}),
    ConversationState.DISCARD: frozenset({ConversationState.PHASE_3}),
    ConversationState.LOST: frozenset({ConversationState.COMPLETED}),
}


def can_transition(
    source_state: ConversationState,
    target_state: ConversationState,
) -> bool:
    return target_state in ALLOWED_STATE_TRANSITIONS.get(source_state, frozenset())

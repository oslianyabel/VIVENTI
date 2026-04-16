from __future__ import annotations

from enum import StrEnum

from chatbot.domain.conversation_states import ConversationState


class GoogleSheetsState(StrEnum):
    NEW = "nuevo"
    IN_QUALIFICATION = "en_calificacion"
    QUALIFIED = "calificado"
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    FOLLOW_UP_3 = "follow_up_3"
    DEMO_SCHEDULED = "demo_agendada"
    LOST = "perdido"
    NOT_QUALIFIED = "no_calificado"


def map_conversation_state_to_sheets(
    state: ConversationState,
    follow_up_count: int = 0,
) -> GoogleSheetsState:
    if state == ConversationState.PHASE_1:
        return GoogleSheetsState.NEW
    if state == ConversationState.PHASE_2:
        return GoogleSheetsState.IN_QUALIFICATION
    if state == ConversationState.PHASE_3:
        follow_up_mapping: dict[int, GoogleSheetsState] = {
            0: GoogleSheetsState.QUALIFIED,
            1: GoogleSheetsState.FOLLOW_UP_1,
            2: GoogleSheetsState.FOLLOW_UP_2,
        }
        return follow_up_mapping.get(follow_up_count, GoogleSheetsState.FOLLOW_UP_3)
    if state == ConversationState.COMPLETED:
        return GoogleSheetsState.DEMO_SCHEDULED
    if state == ConversationState.LOST:
        return GoogleSheetsState.LOST
    return GoogleSheetsState.NOT_QUALIFIED

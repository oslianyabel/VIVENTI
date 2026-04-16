"""Lead orchestrator — coordinates qualification, state transitions and persistence.

Module-level async functions (no class needed since there is no internal state).
"""

from __future__ import annotations

import logging
from typing import Any

from chatbot.ai_agent.qualification_subagent import QualificationResult
from chatbot.db.services import services
from chatbot.domain.qualification import QualificationAnswers
from chatbot.services.conversation_state_service import conversation_state_service
from chatbot.services.qualification_service import evaluate_qualification

logger = logging.getLogger(__name__)


async def orchestrate_after_phase_2(
    phone: str,
    answers: QualificationAnswers,
    context_messages: list[str] | None = None,
) -> QualificationResult:
    """Evaluate qualification, persist inferred fields, and execute transition.

    Args:
        phone: User phone number.
        answers: The 6 PHASE_2 answers collected from the user.
        context_messages: Optional recent conversation messages for context.

    Returns:
        QualificationResult so the calling layer can decide the response.
    """
    logger.info("[lead_orchestrator] orchestrate_after_phase_2 phone=%s", phone)

    result = await evaluate_qualification(answers, context_messages)

    update_fields: dict[str, Any] = {}
    if result.experience_type:
        update_fields["experience_type"] = result.experience_type
    if result.country:
        update_fields["country"] = result.country
    if result.reservation_method:
        update_fields["reservation_method"] = result.reservation_method
    if result.monthly_reservations is not None:
        update_fields["monthly_reservations"] = result.monthly_reservations
    if result.payment_method:
        update_fields["payment_method"] = result.payment_method
    if result.has_instagram is not None:
        update_fields["has_instagram"] = "si" if result.has_instagram else "no"
    if result.uses_instagram_for_sales is not None:
        update_fields["uses_instagram_for_sales"] = (
            "si" if result.uses_instagram_for_sales else "no"
        )
    if result.main_pain_point:
        update_fields["main_pain_point"] = result.main_pain_point
    update_fields["is_qualified"] = result.qualifies
    if result.disqualification_reason:
        update_fields["disqualification_reason"] = result.disqualification_reason.value
    if result.notes:
        update_fields["notes"] = result.notes

    if update_fields:
        await services.update_user(phone, **update_fields)

    if result.qualifies:
        await conversation_state_service.phase_2_to_phase_3(phone)
        logger.info("[lead_orchestrator] %s qualified → PHASE_3", phone)
    else:
        await conversation_state_service.phase_2_to_discard(phone)
        logger.info(
            "[lead_orchestrator] %s disqualified → DISCARD (reason=%s)",
            phone,
            result.disqualification_reason,
        )

    return result


async def re_evaluate_discard(
    phone: str,
    context_messages: list[str],
) -> QualificationResult:
    """Re-evaluate a DISCARD user when they send a new message.

    Args:
        phone: User phone number.
        context_messages: Recent conversation messages including new context.

    Returns:
        QualificationResult with the updated classification.
    """
    logger.info("[lead_orchestrator] re_evaluate_discard phone=%s", phone)

    user = await services.get_user(phone)
    answers = QualificationAnswers(
        phase_2_answer_1=getattr(user, "phase_2_answer_1", None),
        phase_2_answer_2=getattr(user, "phase_2_answer_2", None),
        phase_2_answer_3=getattr(user, "phase_2_answer_3", None),
        phase_2_answer_4=getattr(user, "phase_2_answer_4", None),
        phase_2_answer_5=getattr(user, "phase_2_answer_5", None),
        phase_2_answer_6=getattr(user, "phase_2_answer_6", None),
    )

    result = await evaluate_qualification(answers, context_messages)

    if result.qualifies:
        update_fields: dict[str, Any] = {
            "is_qualified": True,
            "disqualification_reason": None,
            "follow_up_count": 0,
            "last_follow_up_at": None,
        }
        if result.experience_type:
            update_fields["experience_type"] = result.experience_type
        if result.country:
            update_fields["country"] = result.country
        if result.reservation_method:
            update_fields["reservation_method"] = result.reservation_method
        if result.monthly_reservations is not None:
            update_fields["monthly_reservations"] = result.monthly_reservations
        if result.payment_method:
            update_fields["payment_method"] = result.payment_method
        if result.has_instagram is not None:
            update_fields["has_instagram"] = "si" if result.has_instagram else "no"
        if result.uses_instagram_for_sales is not None:
            update_fields["uses_instagram_for_sales"] = (
                "si" if result.uses_instagram_for_sales else "no"
            )
        if result.main_pain_point:
            update_fields["main_pain_point"] = result.main_pain_point
        if result.notes:
            update_fields["notes"] = result.notes

        await services.update_user(phone, **update_fields)
        await conversation_state_service.discard_to_phase_3(phone)
        logger.info("[lead_orchestrator] %s re-qualified → PHASE_3", phone)
    else:
        logger.info("[lead_orchestrator] %s still disqualified", phone)

    return result


async def persist_user_data_from_message(
    phone: str,
    field_updates: dict[str, Any],
) -> None:
    """Persist user data fields extracted during conversation.

    Called by agent tools whenever the user shares personal data during any phase.
    """
    if field_updates:
        await services.update_user(phone, **field_updates)
        logger.debug(
            "[lead_orchestrator] Persisted fields for %s: %s",
            phone,
            list(field_updates.keys()),
        )

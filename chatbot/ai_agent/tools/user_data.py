"""User data persistence tools for the VIVENTI agent."""

from __future__ import annotations

import logging

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from chatbot.ai_agent.dependencies import AgentDeps

logger = logging.getLogger(__name__)


async def update_user_data(
    ctx: RunContext[AgentDeps],
    field_name: str,
    field_value: str,
) -> str:
    """Persist a user data field to the database.

    Call this tool every time the user shares personal data (name, email,
    establishment_name, experience_name, language, etc.).

    Args:
        ctx: Agent run context (injected automatically).
        field_name: The database field name to update (e.g., "name", "email",
            "establishment_name", "experience_name", "language").
        field_value: The value to store.

    Returns:
        Confirmation of the update.
    """
    logger.info(
        "[update_user_data] phone=%s field=%s value=%s",
        ctx.deps.user_phone,
        field_name,
        field_value,
    )
    allowed_fields: set[str] = {
        "name",
        "email",
        "experience_name",
        "establishment_name",
        "experience_type",
        "country",
        "reservation_method",
        "monthly_reservations",
        "payment_method",
        "has_instagram",
        "uses_instagram_for_sales",
        "main_pain_point",
        "language",
        "notes",
    }
    if field_name not in allowed_fields:
        raise ModelRetry(
            f"Campo '{field_name}' no permitido. Campos válidos: {', '.join(sorted(allowed_fields))}"
        )

    from chatbot.db.services import services

    await services.update_user(ctx.deps.user_phone, **{field_name: field_value})
    return f"Campo '{field_name}' actualizado."

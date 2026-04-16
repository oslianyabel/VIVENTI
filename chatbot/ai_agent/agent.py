from __future__ import annotations

import logging

from pydantic_ai import Agent, RunContext
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition

from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.ai_agent.instructions import register_instructions
from chatbot.ai_agent.models import GoogleModel
from chatbot.ai_agent.prompts import SYSTEM_PROMPT
from chatbot.ai_agent.tools.date_resolver import resolve_relative_date
from chatbot.ai_agent.tools.google_calendar import (
    cancel_google_calendar_event,
    create_google_calendar_event,
    get_available_slots,
    get_user_demo_scheduled,
    update_google_calendar_event,
)
from chatbot.ai_agent.tools.google_sheets import (
    add_google_sheets_data,
    get_google_sheets_data,
)
from chatbot.ai_agent.tools.qualification import (
    evaluate_and_transition_phase_2,
    re_evaluate_discard_answers,
    save_phase_2_answers,
)
from chatbot.ai_agent.tools.state_transitions import (
    phase_1_to_phase_2,
    phase_3_to_lost,
)
from chatbot.ai_agent.tools.user_data import update_user_data

logger = logging.getLogger(__name__)

FALLBACK_MODEL: str = GoogleModel.Gemini_3_Flash_Preview


def _once_per_turn(tool_name: str):
    """Return a `prepare` callback that disables the tool after its first call."""

    async def prepare(
        ctx: RunContext[AgentDeps], tool_def: ToolDefinition
    ) -> ToolDefinition | None:
        if tool_name in ctx.deps.called_tools:
            logger.debug(
                "[once_per_turn] %s already called this turn — disabled", tool_name
            )
            return None
        return tool_def

    return prepare


AGENT_TOOLS = [
    # Date resolution
    resolve_relative_date,
    # State transitions
    phase_1_to_phase_2,
    phase_3_to_lost,
    # Read-only
    get_available_slots,
    get_google_sheets_data,
    # Data persistence
    update_user_data,
    save_phase_2_answers,
    # Composite
    evaluate_and_transition_phase_2,
    re_evaluate_discard_answers,
    # Google Calendar
    create_google_calendar_event,
    update_google_calendar_event,
    cancel_google_calendar_event,
    get_user_demo_scheduled,
    # Google Sheets
    add_google_sheets_data,
]


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

_viventi_agent: Agent[AgentDeps, str] | None = None


def reset_viventi_agent() -> None:
    """Descarta el singleton para que la próxima llamada lo recree con el prompt actualizado."""
    global _viventi_agent  # noqa: PLW0603
    _viventi_agent = None
    logger.info("[reset_viventi_agent] Singleton descartado")


def get_viventi_agent() -> Agent[AgentDeps, str]:
    """Return the singleton VIVENTI agent, creating it on first call."""
    global _viventi_agent  # noqa: PLW0603
    if _viventi_agent is None:
        _viventi_agent = Agent(
            model=GoogleModel.Gemini_Flash_Latest,
            system_prompt=SYSTEM_PROMPT,
            deps_type=AgentDeps,
            tools=AGENT_TOOLS,
            model_settings=ModelSettings(temperature=0),
        )
        register_instructions(_viventi_agent)
        logger.info("VIVENTI agent initialized with %d tools", len(AGENT_TOOLS))
    return _viventi_agent

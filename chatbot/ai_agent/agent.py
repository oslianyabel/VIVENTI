from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic_ai import Agent, RunContext
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition

from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.ai_agent.models import GoogleModel
from chatbot.ai_agent.prompts import SYSTEM_PROMPT
from chatbot.ai_agent.tools.date_resolver import resolve_relative_date

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
    # Date resolution sub-agent
    resolve_relative_date,
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

        @_viventi_agent.instructions
        def reply_in_user_language_prompt(
            ctx: RunContext[AgentDeps],
        ) -> str:
            return (
                "Always reply in the same language as the user's most recent message. "
                "Ignore the language used by this system prompt, tool schemas, tool outputs, "
                "or ERP data. If any tool returns content in a different language, translate "
                "or adapt it before answering. If the user writes in Spanish, use Rioplatense Spanish."
            )

        @_viventi_agent.instructions
        def current_datetime_prompt(
            ctx: RunContext[AgentDeps],
        ) -> str:
            now = datetime.now(tz=timezone.utc).astimezone()
            return (
                f"Current date and time: {now.strftime('%A %d %B %Y, %H:%M')} "
                f"(server timezone: {now.strftime('%Z %z')}). "
                "Use this date to resolve expressions such as tomorrow, next week, next month, "
                "or in N days."
            )

        logger.info("VIVENTI agent initialized with %d tools", len(AGENT_TOOLS))
    return _viventi_agent

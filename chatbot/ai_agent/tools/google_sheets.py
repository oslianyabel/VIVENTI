"""Google Sheets agent tools — thin wrappers around the Sheets service."""

from __future__ import annotations

import logging

from pydantic_ai import RunContext

from chatbot.ai_agent.dependencies import AgentDeps
from chatbot.services.google_sheets_service import GoogleSheetsError
from chatbot.services.google_sheets_service import get_all_rows as _get_all_rows
from chatbot.services.google_sheets_sync import sync_user_to_sheets

logger = logging.getLogger(__name__)


async def get_google_sheets_data(
    ctx: RunContext[AgentDeps],
) -> str:
    """Retrieve all rows from the Google Sheets lead tracker.

    Use this tool to view the current state of all leads in the spreadsheet.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Formatted summary of all rows, or an error message.
    """
    logger.info("[get_google_sheets_data] Fetching all rows")
    try:
        rows = await _get_all_rows()
    except GoogleSheetsError as exc:
        logger.error("[get_google_sheets_data] %s", exc)
        return f"Error al leer Google Sheets: {exc}"

    if not rows:
        return "No hay datos en Google Sheets."

    lines: list[str] = [f"Total de filas: {len(rows)}\n"]
    for row in rows[:50]:
        phone = row.get("telefono", "?")
        name = row.get("nombre_contacto", "?")
        state = row.get("estado", "?")
        lines.append(f"• {phone} | {name} | {state}")

    if len(rows) > 50:
        lines.append(f"\n... y {len(rows) - 50} filas más.")
    return "\n".join(lines)


async def add_google_sheets_data(
    ctx: RunContext[AgentDeps],
) -> str:
    """Create or update the Google Sheets row for the current user.

    Use this tool to manually sync the current user's data to Google Sheets.
    Note: This is also triggered automatically when conversations reach
    COMPLETED, LOST, or DISCARD states.

    Args:
        ctx: Agent run context (injected automatically).

    Returns:
        Confirmation message.
    """
    phone = ctx.deps.user_phone
    logger.info("[add_google_sheets_data] phone=%s", phone)

    try:
        await sync_user_to_sheets(phone)
    except Exception as exc:
        logger.error("[add_google_sheets_data] %s", exc)
        return f"Error al sincronizar con Google Sheets: {exc}"

    return "Datos sincronizados con Google Sheets."

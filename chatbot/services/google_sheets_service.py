"""Google Sheets API wrapper service.

Provides async functions for reading and writing rows in the VIVENTI leads
spreadsheet via gspread + service account credentials.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from chatbot.core.config import config

logger = logging.getLogger(__name__)

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
PHONE_COLUMN_HEADER: str = "telefono"


class GoogleSheetsError(Exception):
    """Wraps errors from the Google Sheets API."""


def _get_worksheet() -> gspread.Worksheet:
    """Build and return the first worksheet of the configured spreadsheet."""
    credentials = Credentials.from_service_account_file(
        config.GOOGLE_SHEETS_CREDENTIALS_FILE,
        scopes=SCOPES,
    )
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEETS_SPREADSHEET_ID)
    return spreadsheet.sheet1


async def _run_in_executor(func, *args):
    """Run a blocking gspread call in the default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


async def get_all_rows() -> list[dict[str, Any]]:
    """Read all rows from the first sheet.

    Returns:
        List of dicts keyed by column headers.
    """
    try:
        ws = _get_worksheet()
        rows: list[dict[str, Any]] = await _run_in_executor(ws.get_all_records)
    except Exception as exc:
        raise GoogleSheetsError(f"Failed to read all rows: {exc}") from exc

    logger.info("[google_sheets] Read %d rows", len(rows))
    return rows


async def get_row_by_phone(phone: str) -> dict[str, Any] | None:
    """Search for a row by the phone column.

    Args:
        phone: Phone number to search for.

    Returns:
        Row dict or None if not found.
    """
    try:
        ws = _get_worksheet()
        all_records: list[dict[str, Any]] = await _run_in_executor(ws.get_all_records)
    except Exception as exc:
        raise GoogleSheetsError(f"Failed to search by phone: {exc}") from exc

    for row in all_records:
        if str(row.get(PHONE_COLUMN_HEADER, "")) == phone:
            return row
    return None


async def upsert_row(data: dict[str, Any]) -> None:
    """Insert or update a row based on the phone column.

    If a row with the same phone exists, update it in place.
    Otherwise, append a new row.

    Args:
        data: Dict with column header keys and cell values.
    """
    phone = str(data.get(PHONE_COLUMN_HEADER, ""))
    if not phone:
        raise GoogleSheetsError("Cannot upsert row without 'telefono' field")

    try:
        ws = _get_worksheet()
        headers: list[str] = await _run_in_executor(lambda: ws.row_values(1))

        if not headers:
            await _run_in_executor(lambda: ws.append_row(list(data.keys())))
            headers = list(data.keys())

        phone_col_idx: int | None = None
        for i, header in enumerate(headers):
            if header.strip().lower() == PHONE_COLUMN_HEADER:
                phone_col_idx = i + 1
                break

        if phone_col_idx is None:
            raise GoogleSheetsError(
                f"Column '{PHONE_COLUMN_HEADER}' not found in headers: {headers}"
            )

        all_values: list[list[str]] = await _run_in_executor(ws.get_all_values)

        existing_row_idx: int | None = None
        for row_idx, row_values in enumerate(all_values[1:], start=2):
            if len(row_values) >= phone_col_idx:
                cell_value = row_values[phone_col_idx - 1].strip()
                if cell_value == phone:
                    existing_row_idx = row_idx
                    break

        row_data: list[Any] = []
        for header in headers:
            row_data.append(str(data.get(header, "")))

        if existing_row_idx:
            cell_range = f"A{existing_row_idx}"
            await _run_in_executor(
                lambda: ws.update(values=[row_data], range_name=cell_range)
            )
            logger.info(
                "[google_sheets] Updated row %d for phone=%s",
                existing_row_idx,
                phone,
            )
        else:
            await _run_in_executor(lambda: ws.append_row(row_data))
            logger.info("[google_sheets] Appended new row for phone=%s", phone)

    except GoogleSheetsError:
        raise
    except Exception as exc:
        raise GoogleSheetsError(f"Failed to upsert row: {exc}") from exc

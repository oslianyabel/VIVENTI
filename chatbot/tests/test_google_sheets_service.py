# uv run pytest -s chatbot/tests/test_google_sheets_service.py
"""Integration tests for Google Sheets service — real API calls.

These tests read, write and update rows on the real Google Sheets
spreadsheet configured via environment variables.
Tests run sequentially: upsert creates a row, then we read it back,
update it, and finally clean it up.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from chatbot.services.google_sheets_service import (
    get_all_rows,
    get_row_by_phone,
    upsert_row,
)

logger = logging.getLogger(__name__)

_TEST_PHONE = "+0000TEST0000"


async def _sheet_has_telefono_column() -> bool:
    """Check if the spreadsheet has the expected 'telefono' column."""
    rows = await get_all_rows()
    if not rows:
        return False
    return "telefono" in rows[0]


def _make_row_data(state: str = "nuevo") -> dict[str, str]:
    """Build a sample row dict matching the spreadsheet column layout."""
    return {
        "fecha": datetime.now(UTC).strftime("%Y-%m-%d"),
        "telefono": _TEST_PHONE,
        "nombre_contacto": "Test Runner",
        "nombre_establecimiento": "Bodega Test",
        "tipo_experiencia": "bodega",
        "pais": "Argentina",
        "metodo_reserva_actual": "manual",
        "reservas_por_mes": "10",
        "metodo_cobro": "efectivo",
        "tiene_instagram": "si",
        "usa_instagram_para_ventas": "no",
        "dolor_principal": "test pain point",
        "calificado": "si",
        "razon_no_califica": "",
        "estado": state,
        "fecha_demo": "",
        "idioma": "es",
        "notas": "Fila creada por test suite — borrar si queda",
    }


# ── 1. get_all_rows ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_rows_returns_list() -> None:
    """get_all_rows should return a list of dicts without errors."""
    rows = await get_all_rows()

    assert isinstance(rows, list)
    if rows:
        assert isinstance(rows[0], dict)
    print(f"[OK] get_all_rows returned {len(rows)} row(s)")


# ── 2. upsert_row (insert) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_row_inserts_new() -> None:
    """upsert_row should insert a new row when the phone doesn't exist."""
    if not await _sheet_has_telefono_column():
        pytest.skip(
            "Spreadsheet lacks 'telefono' column — set up VIVENTI headers first"
        )

    data = _make_row_data(state="nuevo")

    # Ensure no leftover from previous failed runs
    existing = await get_row_by_phone(_TEST_PHONE)
    if existing:
        print("[SETUP] Test phone already exists — will be overwritten by upsert")

    await upsert_row(data)
    print(f"[OK] upsert_row completed for phone={_TEST_PHONE}")


# ── 3. get_row_by_phone ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_row_by_phone_finds_inserted() -> None:
    """get_row_by_phone should find the row we just inserted."""
    if not await _sheet_has_telefono_column():
        pytest.skip(
            "Spreadsheet lacks 'telefono' column — set up VIVENTI headers first"
        )

    row = await get_row_by_phone(_TEST_PHONE)

    assert row is not None, f"Row for {_TEST_PHONE} not found"
    assert str(row.get("telefono")) == _TEST_PHONE
    print(f"[OK] get_row_by_phone found row with keys: {list(row.keys())}")


# ── 4. upsert_row (update) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_row_updates_existing() -> None:
    """upsert_row should update the existing row when phone matches."""
    if not await _sheet_has_telefono_column():
        pytest.skip(
            "Spreadsheet lacks 'telefono' column — set up VIVENTI headers first"
        )

    data = _make_row_data(state="calificado")
    data["nombre_contacto"] = "Test Runner UPDATED"
    data["notas"] = "Actualizado por test suite"

    await upsert_row(data)

    # Verify update
    row = await get_row_by_phone(_TEST_PHONE)
    assert row is not None
    assert str(row.get("telefono")) == _TEST_PHONE
    print(f"[OK] upsert_row updated existing row: {row}")


# ── 5. get_row_by_phone (not found) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_row_by_phone_returns_none_for_unknown() -> None:
    """get_row_by_phone should return None for a non-existent phone."""
    row = await get_row_by_phone("+9999999999999")

    assert row is None
    print("[OK] get_row_by_phone returned None for unknown phone")


# ── 6. cleanup — remove test row ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_remove_test_row() -> None:
    """Remove the test row to leave the spreadsheet clean."""
    if not await _sheet_has_telefono_column():
        pytest.skip("Spreadsheet lacks 'telefono' column — nothing to clean")

    import gspread
    from google.oauth2.service_account import Credentials

    from chatbot.core.config import config
    from chatbot.services.google_sheets_service import SCOPES

    credentials = Credentials.from_service_account_file(
        config.GOOGLE_SHEETS_CREDENTIALS_FILE,
        scopes=SCOPES,
    )
    gc = gspread.authorize(credentials)
    ws = gc.open_by_key(config.GOOGLE_SHEETS_SPREADSHEET_ID).sheet1

    all_values = ws.get_all_values()
    deleted = False
    for row_idx, row_values in enumerate(all_values, start=1):
        if _TEST_PHONE in row_values:
            ws.delete_rows(row_idx)
            deleted = True
            break

    if deleted:
        print(f"[CLEANUP] Deleted test row for {_TEST_PHONE}")
    else:
        print(f"[CLEANUP] Test row for {_TEST_PHONE} not found (already clean)")

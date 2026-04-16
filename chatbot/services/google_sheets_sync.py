"""Google Sheets sync helper — builds row data and syncs to Sheets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from chatbot.db.services import services
from chatbot.domain.conversation_states import ConversationState
from chatbot.domain.google_sync import map_conversation_state_to_sheets
from chatbot.services.google_sheets_service import GoogleSheetsError, upsert_row

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GoogleSheetsRowData:
    """Data model matching the Google Sheets column layout."""

    fecha: str
    telefono: str
    nombre_contacto: str
    email: str
    nombre_establecimiento: str
    tipo_experiencia: str
    pais: str
    metodo_reserva_actual: str
    reservas_por_mes: int | None
    metodo_cobro: str
    tiene_instagram: str
    usa_instagram_para_ventas: str
    dolor_principal: str
    calificado: str
    razon_no_califica: str | None
    estado: str
    fecha_demo: str | None
    idioma: str
    notas: str | None

    def as_dict(self) -> dict[str, Any]:
        """Convert to dict matching the spreadsheet column headers."""
        return {
            "fecha": self.fecha,
            "telefono": self.telefono,
            "nombre_contacto": self.nombre_contacto,
            "email": self.email,
            "nombre_establecimiento": self.nombre_establecimiento,
            "tipo_experiencia": self.tipo_experiencia,
            "pais": self.pais,
            "metodo_reserva_actual": self.metodo_reserva_actual,
            "reservas_por_mes": str(self.reservas_por_mes or ""),
            "metodo_cobro": self.metodo_cobro,
            "tiene_instagram": self.tiene_instagram,
            "usa_instagram_para_ventas": self.usa_instagram_para_ventas,
            "dolor_principal": self.dolor_principal,
            "calificado": self.calificado,
            "razon_no_califica": self.razon_no_califica or "",
            "estado": self.estado,
            "fecha_demo": self.fecha_demo or "",
            "idioma": self.idioma,
            "notas": self.notas or "",
        }


async def build_sheets_row(phone: str) -> GoogleSheetsRowData:
    """Build a GoogleSheetsRowData from user and demo records.

    Args:
        phone: User phone number.

    Returns:
        Populated GoogleSheetsRowData ready for upsert.
    """
    user = await services.get_user(phone)
    demo = await services.get_demo_by_phone(phone)

    state = ConversationState(getattr(user, "conversation_state", "PHASE_1"))
    follow_up_count: int = getattr(user, "follow_up_count", 0) or 0
    sheets_state = map_conversation_state_to_sheets(state, follow_up_count)

    demo_date: str | None = None
    if demo and demo.scheduled_at:
        dt = demo.scheduled_at
        if isinstance(dt, datetime):
            demo_date = dt.strftime("%Y-%m-%d")

    return GoogleSheetsRowData(
        fecha=datetime.now(UTC).strftime("%Y-%m-%d"),
        telefono=phone,
        nombre_contacto=getattr(user, "name", "") or "",
        email=getattr(user, "email", "") or "",
        nombre_establecimiento=getattr(user, "establishment_name", "") or "",
        tipo_experiencia=getattr(user, "experience_type", "") or "",
        pais=getattr(user, "country", "") or "",
        metodo_reserva_actual=getattr(user, "reservation_method", "") or "",
        reservas_por_mes=getattr(user, "monthly_reservations", None),
        metodo_cobro=getattr(user, "payment_method", "") or "",
        tiene_instagram=getattr(user, "has_instagram", "") or "",
        usa_instagram_para_ventas=getattr(user, "uses_instagram_for_sales", "") or "",
        dolor_principal=getattr(user, "main_pain_point", "") or "",
        calificado="true" if getattr(user, "is_qualified", False) else "false",
        razon_no_califica=getattr(user, "disqualification_reason", None),
        estado=sheets_state.value,
        fecha_demo=demo_date,
        idioma=getattr(user, "language", "") or "",
        notas=getattr(user, "notes", None),
    )


async def sync_user_to_sheets(phone: str) -> None:
    """Build and upsert a row for the given user to Google Sheets.

    Args:
        phone: User phone number.
    """
    try:
        row = await build_sheets_row(phone)
        await upsert_row(row.as_dict())
        logger.info("[google_sheets_sync] Synced phone=%s state=%s", phone, row.estado)
    except GoogleSheetsError as exc:
        logger.error("[google_sheets_sync] Failed for phone=%s: %s", phone, exc)
    except Exception as exc:
        logger.error(
            "[google_sheets_sync] Unexpected error for phone=%s: %s", phone, exc
        )

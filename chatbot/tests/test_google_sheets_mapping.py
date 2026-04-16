# uv run pytest -s chatbot/tests/test_google_sheets_mapping.py
from chatbot.domain.conversation_states import ConversationState
from chatbot.domain.google_sync import (
    GoogleSheetsState,
    map_conversation_state_to_sheets,
)
from chatbot.services.google_sheets_sync import GoogleSheetsRowData


class TestMapConversationStateToSheets:
    # PHASE_1 → "nuevo"
    def test_phase_1_maps_to_nuevo(self) -> None:
        result = map_conversation_state_to_sheets(ConversationState.PHASE_1)
        assert result == GoogleSheetsState.NEW

    # PHASE_2 → "en_calificacion"
    def test_phase_2_maps_to_en_calificacion(self) -> None:
        result = map_conversation_state_to_sheets(ConversationState.PHASE_2)
        assert result == GoogleSheetsState.IN_QUALIFICATION

    # PHASE_3 + follow_up_count=0 → "calificado"
    def test_phase_3_no_followup_maps_to_calificado(self) -> None:
        result = map_conversation_state_to_sheets(
            ConversationState.PHASE_3, follow_up_count=0
        )
        assert result == GoogleSheetsState.QUALIFIED

    # PHASE_3 + follow_up_count=1 → "follow_up_1"
    def test_phase_3_followup_1(self) -> None:
        result = map_conversation_state_to_sheets(
            ConversationState.PHASE_3, follow_up_count=1
        )
        assert result == GoogleSheetsState.FOLLOW_UP_1

    # PHASE_3 + follow_up_count=2 → "follow_up_2"
    def test_phase_3_followup_2(self) -> None:
        result = map_conversation_state_to_sheets(
            ConversationState.PHASE_3, follow_up_count=2
        )
        assert result == GoogleSheetsState.FOLLOW_UP_2

    # PHASE_3 + follow_up_count=3 → "follow_up_3"
    def test_phase_3_followup_3(self) -> None:
        result = map_conversation_state_to_sheets(
            ConversationState.PHASE_3, follow_up_count=3
        )
        assert result == GoogleSheetsState.FOLLOW_UP_3

    # PHASE_3 + follow_up_count=5 → "follow_up_3" (fallback)
    def test_phase_3_followup_high_defaults_to_3(self) -> None:
        result = map_conversation_state_to_sheets(
            ConversationState.PHASE_3, follow_up_count=5
        )
        assert result == GoogleSheetsState.FOLLOW_UP_3

    # COMPLETED → "demo_agendada"
    def test_completed_maps_to_demo_agendada(self) -> None:
        result = map_conversation_state_to_sheets(ConversationState.COMPLETED)
        assert result == GoogleSheetsState.DEMO_SCHEDULED

    # LOST → "perdido"
    def test_lost_maps_to_perdido(self) -> None:
        result = map_conversation_state_to_sheets(ConversationState.LOST)
        assert result == GoogleSheetsState.LOST

    # DISCARD → "no_calificado"
    def test_discard_maps_to_no_calificado(self) -> None:
        result = map_conversation_state_to_sheets(ConversationState.DISCARD)
        assert result == GoogleSheetsState.NOT_QUALIFIED


class TestGoogleSheetsRowData:
    # as_dict converts None fields correctly
    def test_as_dict_handles_none_fields(self) -> None:
        row = GoogleSheetsRowData(
            fecha="2025-01-01",
            telefono="+5491112345678",
            nombre_contacto="Test",
            nombre_establecimiento="Bodega X",
            tipo_experiencia="bodega",
            pais="Argentina",
            metodo_reserva_actual="manual",
            reservas_por_mes=None,
            metodo_cobro="efectivo",
            tiene_instagram="si",
            usa_instagram_para_ventas="no",
            dolor_principal="gestión manual",
            calificado="si",
            razon_no_califica=None,
            estado="calificado",
            fecha_demo=None,
            idioma="es",
            notas=None,
        )
        d = row.as_dict()
        assert d["reservas_por_mes"] == ""
        assert d["razon_no_califica"] == ""
        assert d["fecha_demo"] == ""
        assert d["notas"] == ""

    # as_dict converts populated fields correctly
    def test_as_dict_with_all_fields(self) -> None:
        row = GoogleSheetsRowData(
            fecha="2025-01-01",
            telefono="+5491112345678",
            nombre_contacto="Test",
            nombre_establecimiento="Bodega X",
            tipo_experiencia="bodega",
            pais="Argentina",
            metodo_reserva_actual="manual",
            reservas_por_mes=20,
            metodo_cobro="efectivo",
            tiene_instagram="si",
            usa_instagram_para_ventas="si",
            dolor_principal="gestión manual",
            calificado="si",
            razon_no_califica=None,
            estado="demo_agendada",
            fecha_demo="2025-02-01T10:00:00",
            idioma="es",
            notas="Interesado",
        )
        d = row.as_dict()
        assert d["reservas_por_mes"] == "20"
        assert d["telefono"] == "+5491112345678"
        assert d["fecha_demo"] == "2025-02-01T10:00:00"
        assert d["notas"] == "Interesado"

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    phone: str
    name: str | None = None
    email: EmailStr | None = None
    experience_name: str | None = None
    conversation_state: str = "PHASE_1"
    is_qualified: bool | None = None
    disqualification_reason: str | None = None
    follow_up_count: int = 0
    language: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_interaction: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DemoResponse(BaseModel):
    id: int
    user_phone: str
    title: str
    duration_minutes: int
    description: str
    scheduled_at: datetime
    google_calendar_event_id: str | None = None
    upcoming_reminder_sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserResponse):
    phase_2_answer_1: str | None = None
    phase_2_answer_2: str | None = None
    phase_2_answer_3: str | None = None
    phase_2_answer_4: str | None = None
    phase_2_answer_5: str | None = None
    phase_2_answer_6: str | None = None
    establishment_name: str | None = None
    experience_type: str | None = None
    country: str | None = None
    reservation_method: str | None = None
    monthly_reservations: int | None = None
    payment_method: str | None = None
    has_instagram: str | None = None
    uses_instagram_for_sales: str | None = None
    main_pain_point: str | None = None
    notes: str | None = None
    demo: DemoResponse | None = None


class Messages(BaseModel):
    user_phone: str
    role: str | None = None
    message: str | None = None
    tools_used: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SheetsRowResponse(BaseModel):
    fecha: str
    telefono: str
    nombre_contacto: str
    nombre_establecimiento: str
    tipo_experiencia: str
    pais: str
    metodo_reserva_actual: str
    reservas_por_mes: int | None = None
    metodo_cobro: str
    tiene_instagram: str
    usa_instagram_para_ventas: str
    dolor_principal: str
    calificado: str
    razon_no_califica: str | None = None
    estado: str
    fecha_demo: str | None = None
    idioma: str
    notas: str | None = None

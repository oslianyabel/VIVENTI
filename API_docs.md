# VIVENTI API Documentation

Base URL: `http://localhost:8000`

All endpoints under `/chats` require the `X-API-Key` header.

---

## Authentication

All admin endpoints require the following header:

```
X-API-Key: your_admin_api_key
```

---

## Endpoints

### GET /chats/users

List all users with their conversation state.

**Response:** `200 OK`

```json
[
  {
    "phone": "+5491112345678",
    "name": "Juan Pérez",
    "email": "juan@bodega.com",
    "experience_name": "Bodega Vista Alta",
    "conversation_state": "PHASE_3",
    "is_qualified": true,
    "disqualification_reason": null,
    "follow_up_count": 1,
    "language": "es",
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T14:00:00Z",
    "last_interaction": "2025-01-15T14:00:00Z"
  }
]
```

---

### GET /chats/users/{phone}

Get full user details including qualification data and scheduled demo.

**Path parameters:**
- `phone` (string, required) — User phone number (e.g., `+5491112345678`)

**Response:** `200 OK`

```json
{
  "phone": "+5491112345678",
  "name": "Juan Pérez",
  "email": "juan@bodega.com",
  "experience_name": "Bodega Vista Alta",
  "conversation_state": "COMPLETED",
  "is_qualified": true,
  "disqualification_reason": null,
  "follow_up_count": 0,
  "language": "es",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-16T09:00:00Z",
  "last_interaction": "2025-01-16T09:00:00Z",
  "phase_2_answer_1": "Bodega en Mendoza",
  "phase_2_answer_2": "Manual, por teléfono",
  "phase_2_answer_3": "20 por mes",
  "phase_2_answer_4": "Efectivo y transferencia",
  "phase_2_answer_5": "Sí, @bodegavista",
  "phase_2_answer_6": "Gestión manual de reservas",
  "establishment_name": "Bodega Vista Alta",
  "experience_type": "bodega",
  "country": "Argentina",
  "reservation_method": "manual",
  "monthly_reservations": 20,
  "payment_method": "efectivo",
  "has_instagram": "si",
  "uses_instagram_for_sales": "si",
  "main_pain_point": "gestión manual",
  "notes": null,
  "demo": {
    "id": 1,
    "user_phone": "+5491112345678",
    "title": "Demo VIVENTI - Bodega Vista Alta",
    "duration_minutes": 30,
    "description": "Demo del sistema de reservas",
    "scheduled_at": "2025-01-20T10:00:00Z",
    "google_calendar_event_id": "abc123",
    "upcoming_reminder_sent_at": null,
    "created_at": "2025-01-16T09:00:00Z",
    "updated_at": null
  }
}
```

**Error:** `404 Not Found` — User not found.

---

### GET /chats/messages/{phone}

List all conversation messages for a user.

**Path parameters:**
- `phone` (string, required) — User phone number

**Response:** `200 OK`

```json
[
  {
    "user_phone": "+5491112345678",
    "role": "user",
    "message": "Hola, tengo una bodega en Mendoza",
    "tools_used": null,
    "created_at": "2025-01-15T10:30:00Z"
  },
  {
    "user_phone": "+5491112345678",
    "role": "assistant",
    "message": "¡Hola! Bienvenido a VIVENTI...",
    "tools_used": "phase_1_to_phase_2",
    "created_at": "2025-01-15T10:30:05Z"
  }
]
```

---

### GET /chats/sheets/{phone}

Get the Google Sheets row data for a user.

**Path parameters:**
- `phone` (string, required) — User phone number

**Response:** `200 OK`

```json
{
  "fecha": "2025-01-15",
  "telefono": "+5491112345678",
  "nombre_contacto": "Juan Pérez",
  "nombre_establecimiento": "Bodega Vista Alta",
  "tipo_experiencia": "bodega",
  "pais": "Argentina",
  "metodo_reserva_actual": "manual",
  "reservas_por_mes": 20,
  "metodo_cobro": "efectivo",
  "tiene_instagram": "si",
  "usa_instagram_para_ventas": "si",
  "dolor_principal": "gestión manual",
  "calificado": "si",
  "razon_no_califica": null,
  "estado": "demo_agendada",
  "fecha_demo": "2025-01-20T10:00:00",
  "idioma": "es",
  "notas": null
}
```

**Error:** `404 Not Found` — Row not found in Google Sheets.

---

### GET /health

Health check endpoint (no authentication required).

**Response:** `200 OK`

```json
{
  "status": "ok"
}
```

# VIVENTI — Lead Qualification & Demo Scheduling Chatbot

AI-powered chatbot for **VIVENTI**, a platform that connects tourism experience operators (wineries, gastro-tourism, adventure, wellness) with a digital reservation management system. The bot qualifies leads, schedules demos, and automates follow-ups through WhatsApp and Telegram.

---

## Use Cases

- Qualify tourism experience operators as potential VIVENTI clients
- Schedule product demos via Google Calendar
- Automate follow-up reminders for inactive leads
- Sync lead data to Google Sheets for sales tracking
- Support multi-language conversations (Spanish, English, Portuguese)

---

## Key Features

- **6-state conversation flow**: PHASE_1 → PHASE_2 → PHASE_3 → COMPLETED / DISCARD / LOST
- **AI-driven lead qualification** via a dedicated subagent with structured output
- **Google Calendar integration** for demo scheduling with collision detection
- **Google Sheets sync** triggered automatically on state transitions
- **Automated follow-ups** (up to 3, spaced ≥4h apart) for inactive qualified leads
- **Demo reminders** sent 60 minutes before scheduled demos
- **Multi-channel support**: WhatsApp Business API and Telegram
- **DISCARD re-evaluation**: users previously disqualified are re-assessed on new messages
- **Audio transcription** (Speech-to-Text) support
- **Developer error notifications** via Telegram
- **Error monitoring** with Sentry

---

## Technologies

| Layer | Technology |
|---|---|
| Language | Python 3.13+ |
| API framework | FastAPI |
| AI agent | PydanticAI |
| AI model | Google Gemini |
| Messaging — WhatsApp | Meta WhatsApp Business API |
| Messaging — Telegram | python-telegram-bot |
| Database | PostgreSQL (asyncpg + SQLAlchemy + databases) |
| Google Calendar | Google Calendar API v3 (service account) |
| Google Sheets | gspread (service account) |
| Audio | ffmpeg + Speech-to-Text |
| Error monitoring | Sentry |
| Package manager | uv |

---

## Architecture

```
VIVENTI/
├── chatbot/
│   ├── ai_agent/           # PydanticAI agent, prompts, subagents, tools
│   │   └── tools/          # Google Calendar, Google Sheets, date resolution
│   ├── api/                # FastAPI routers: WhatsApp webhook, Telegram, admin API
│   │   └── utils/          # Message handling, queue, webhook parsing, security
│   ├── audio/              # Audio conversion and speech-to-text
│   ├── core/               # Config, logging and Sentry setup
│   ├── db/                 # Database schema (users, messages, demos) and services
│   ├── domain/             # Conversation states, google sync mappings, qualification
│   ├── messaging/          # WhatsApp and Telegram notification clients
│   ├── reminders/          # Background scheduler, follow-up and demo reminder workers
│   └── services/           # Business logic: orchestration, state machine, processors
├── context/                # Specs, plans, research docs
├── scripts/                # Manual test and debug scripts
├── sql/                    # Database migration scripts
├── static/                 # API docs, prompt files
└── docker/                 # Container configuration
```

**Request flow:**
1. Message received via WhatsApp webhook or Telegram
2. Pre-agent processing: update last interaction, re-evaluate DISCARD users
3. PydanticAI agent runs with injected dependencies (user phone, channel, DB)
4. Agent uses tools for state transitions, Calendar, Sheets, and qualification
5. Response sent back through the corresponding channel

**Background workers:**

| Worker | File | Interval | Purpose |
|---|---|---|---|
| Follow-up | `chatbot/reminders/follow_up_worker.py` | 15 min | Sends up to 3 re-engagement messages to PHASE_3 leads without a demo, transitions to LOST after 3 |
| Demo reminder | `chatbot/reminders/demo_reminder_worker.py` | 15 min | Sends a reminder 60 minutes before scheduled demos |

---

## Environment Variables

Create a `.env` file in the project root:

```env
# General
ENV_STATE=dev                    # dev | prod
DATABASE_URL=postgresql://user:password@host:5432/dbname

# AI
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=your_google_api_key

# Meta WhatsApp Business API
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_verify_token
WHATSAPP_BOT_NUMBER=+your_bot_number
WABA_ID=your_waba_id

# Google Calendar
GOOGLE_CALENDAR_ID=your_calendar_id

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE=path/to/service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id

# Sentry
SENTRY_DSN=https://...@sentry.io/...

# Server
SERVER_HOST=https://your-server.com

# Auth
ADMIN_API_KEY=your_admin_api_key

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_DEV_CHAT_ID=your_chat_id
TELEGRAM_BOT_TOKEN_NOTIFIER=your_notifier_bot_token

# Other
MINUTES_BETWEEN_IMAGES=30
USE_FFMPEG=true
```

---

## Database

**PostgreSQL** with three tables:

- `users` — contact info, qualification data, conversation state, follow-up tracking
- `messages` — full conversation history per user, including tool calls
- `demos` — scheduled demo records linked to Google Calendar events

---

## APIs Consumed

| API | Purpose |
|---|---|
| Google Gemini AI | Natural language understanding and response generation |
| Google Calendar API v3 | Demo scheduling, availability checking, event management |
| Google Sheets API v4 | Lead data sync for sales tracking |
| Meta WhatsApp Business API | Send and receive WhatsApp messages |
| Telegram Bot API | Send and receive Telegram messages |

---

## API Keys Required

- `GOOGLE_API_KEY` — Google Gemini AI
- `WHATSAPP_ACCESS_TOKEN` — Meta WhatsApp Business API
- `TELEGRAM_BOT_TOKEN` — Telegram Bot API
- `TELEGRAM_BOT_TOKEN_NOTIFIER` — Telegram notifications bot
- `ADMIN_API_KEY` — Admin API authentication
- Google service account JSON file — Calendar + Sheets access

---

## External Services

- **Google Cloud**: Calendar API + Sheets API (service account)
- **Meta**: WhatsApp Business API
- **Telegram**: Bot API
- **Sentry**: Error tracking and monitoring

---

## How to Run

### Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) installed
- PostgreSQL instance running
- `.env` file configured

### Install dependencies

```bash
uv sync
```

### Run the API server (WhatsApp webhooks + admin API)

```bash
uv run uvicorn chatbot.api.main:app --host 0.0.0.0 --port 8000
```

### Run the Telegram bot

```bash
uv run python scripts/run_telegram_bot.py
```

### API Documentation (Swagger)

Once the server is running, open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

---

## Running Tests

```bash
uv run pytest
```

Run a specific test file with output:

```bash
uv run pytest -s chatbot/tests/test_google_sheets_mapping.py
```

---

## Areas for Improvement

- Add WhatsApp message templates for follow-up reminders
- Implement OCR support for image processing
- Add structured agent outputs (`answer`, `reasoning`, `needs_human`)
- Add automated integration tests with real DB
- Implement webhook retry logic for failed message deliveries
- Add admin dashboard frontend

---

© Osliani Figueiras Saucedo

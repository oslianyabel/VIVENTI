import logging
from contextlib import asynccontextmanager

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chatbot.api.chat_router import router as chat_router
from chatbot.api.utils.filesystem import create_dirs
from chatbot.api.whatsapp_router import router as whatsapp_router
from chatbot.core.config import config
from chatbot.core.logging_conf import init_logging
from chatbot.core.sentry import init_sentry
from chatbot.db.services import services
from chatbot.messaging.telegram_notifier import notify_startup
from chatbot.reminders.scheduler import start_scheduler
from chatbot.services import conversation_state_service

init_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VIVENTI Bot")
    await services.database.connect()
    init_sentry()
    create_dirs()
    await conversation_state_service.preload_active_users()
    scheduler_task = await start_scheduler()
    await notify_startup()

    yield

    scheduler_task.cancel()
    try:
        await services.database.disconnect()
        logger.info("Disconnected from database")
    except Exception as exc:
        logger.error(f"Error disconnecting from database: {exc}")


app = FastAPI(
    title="VIVENTI Bot",
    description="VIVENTI WhatsApp Bot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router, prefix="/whatsapp")
app.include_router(chat_router)


@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "environment": config.ENV_STATE,
        "USE_FFMPEG": config.USE_FFMPEG,
        "WHATSAPP_BOT_NUMBER": config.WHATSAPP_BOT_NUMBER,
    }


@app.get("/")
async def root():
    logger.info("Root")
    return {
        "message": "Welcome to VIVENTI Bot",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0

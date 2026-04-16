import logging
import time

import databases
import sqlalchemy
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func

from chatbot.core.config import config
from chatbot.domain.conversation_states import INITIAL_CONVERSATION_STATE

logger = logging.getLogger(__name__)

metadata = sqlalchemy.MetaData()

users_table = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("phone", String, primary_key=True),
    sqlalchemy.Column("name", String, nullable=True),
    sqlalchemy.Column("email", String, nullable=True),
    sqlalchemy.Column("experience_name", String, nullable=True),
    sqlalchemy.Column("phase_2_answer_1", Text, nullable=True),
    sqlalchemy.Column("phase_2_answer_2", Text, nullable=True),
    sqlalchemy.Column("phase_2_answer_3", Text, nullable=True),
    sqlalchemy.Column("phase_2_answer_4", Text, nullable=True),
    sqlalchemy.Column("phase_2_answer_5", Text, nullable=True),
    sqlalchemy.Column("phase_2_answer_6", Text, nullable=True),
    sqlalchemy.Column("establishment_name", String, nullable=True),
    sqlalchemy.Column("experience_type", String, nullable=True),
    sqlalchemy.Column("country", String, nullable=True),
    sqlalchemy.Column("reservation_method", String, nullable=True),
    sqlalchemy.Column("monthly_reservations", Integer, nullable=True),
    sqlalchemy.Column("payment_method", String, nullable=True),
    sqlalchemy.Column("has_instagram", String, nullable=True),
    sqlalchemy.Column("uses_instagram_for_sales", String, nullable=True),
    sqlalchemy.Column("main_pain_point", Text, nullable=True),
    sqlalchemy.Column("is_qualified", Boolean, nullable=True),
    sqlalchemy.Column("disqualification_reason", String, nullable=True),
    sqlalchemy.Column(
        "conversation_state",
        String,
        nullable=False,
        server_default=INITIAL_CONVERSATION_STATE.value,
    ),
    sqlalchemy.Column("language", String, nullable=True),
    sqlalchemy.Column("notes", Text, nullable=True),
    sqlalchemy.Column("follow_up_count", Integer, nullable=False, server_default="0"),
    sqlalchemy.Column("last_follow_up_at", DateTime, nullable=True),
    sqlalchemy.Column("address", String, nullable=True),
    sqlalchemy.Column("resume", Text, nullable=True),
    sqlalchemy.Column("permissions", String, default="user"),
    sqlalchemy.Column("created_at", DateTime, default=func.now()),
    sqlalchemy.Column("updated_at", DateTime, default=func.now()),
    sqlalchemy.Column("last_interaction", DateTime, default=func.now()),
)

message_table = sqlalchemy.Table(
    "messages",
    metadata,
    sqlalchemy.Column("id", Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("user_phone", ForeignKey("users.phone"), nullable=False),
    sqlalchemy.Column("role", String, nullable=False),
    sqlalchemy.Column("message", String, nullable=False),
    sqlalchemy.Column("tools_used", Text, nullable=True),
    sqlalchemy.Column(
        "active", Boolean, nullable=False, server_default=sqlalchemy.true()
    ),
    sqlalchemy.Column("created_at", DateTime, default=func.now()),
)

demos_table = sqlalchemy.Table(
    "demos",
    metadata,
    sqlalchemy.Column("id", Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column(
        "user_phone",
        ForeignKey("users.phone", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    sqlalchemy.Column("title", String, nullable=False),
    sqlalchemy.Column("duration_minutes", Integer, nullable=False),
    sqlalchemy.Column("description", Text, nullable=False),
    sqlalchemy.Column("scheduled_at", DateTime, nullable=False),
    sqlalchemy.Column("google_calendar_event_id", String, nullable=True),
    sqlalchemy.Column("upcoming_reminder_sent_at", DateTime, nullable=True),
    sqlalchemy.Column("created_at", DateTime, default=func.now()),
    sqlalchemy.Column("updated_at", DateTime, default=func.now()),
)


# Database connection retry settings
DB_MAX_RETRIES = 5
DB_RETRY_DELAY = 3  # seconds


def init_db() -> databases.Database:
    db_url = config.DATABASE_URL  # type: ignore
    # Fix for SQLAlchemy: postgres:// is not valid, must be postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    logger.info(
        f"🔌 Initializing database connection to: {db_url.split('@')[1] if '@' in db_url else 'unknown'}"
    )

    engine = sqlalchemy.create_engine(db_url)

    # Retry logic for create_all (waits for DB to be ready)
    for attempt in range(1, DB_MAX_RETRIES + 1):
        try:
            logger.info(
                f"🔄 Attempting to create tables (attempt {attempt}/{DB_MAX_RETRIES})..."
            )
            # Only create tables that don't already exist
            metadata.create_all(engine, checkfirst=True)
            logger.info("✅ Database tables created/verified successfully")
            break
        except sqlalchemy.exc.ProgrammingError as prog_exc:
            if "permission denied" in str(prog_exc).lower():
                logger.warning(
                    "⚠️ No CREATE privilege on schema — assuming tables already exist"
                )
                break
            logger.error(
                f"❌ Database connection failed (attempt {attempt}/{DB_MAX_RETRIES}): {prog_exc}"
            )
            if attempt < DB_MAX_RETRIES:
                logger.info(f"⏳ Retrying in {DB_RETRY_DELAY} seconds...")
                time.sleep(DB_RETRY_DELAY)
            else:
                raise
        except Exception as exc:
            logger.error(
                f"❌ Database connection failed (attempt {attempt}/{DB_MAX_RETRIES}): {exc}"
            )
            if attempt < DB_MAX_RETRIES:
                logger.info(f"⏳ Retrying in {DB_RETRY_DELAY} seconds...")
                time.sleep(DB_RETRY_DELAY)
            else:
                logger.error(
                    f"💀 All {DB_MAX_RETRIES} database connection attempts failed"
                )
                raise

    database = databases.Database(db_url, force_rollback=False)
    return database

import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import asyncpg
import sqlalchemy
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chatbot.db.schema import (
    demos_table,
    init_db,
    message_table,
    users_table,
)
from chatbot.domain.conversation_states import (
    INITIAL_CONVERSATION_STATE,
    ConversationState,
)
from chatbot.domain.demo import DemoRecord

logger = logging.getLogger(__name__)


class Services:
    def __init__(self, database, debug=False):
        self.database = database
        self.debug = debug

    async def get_user(self, phone: str):
        query = users_table.select().where(users_table.c.phone == phone)
        if self.debug:
            logger.debug(query)

        user = await self.database.fetch_one(query)
        return user

    async def get_all_users(self):
        query = users_table.select()
        if self.debug:
            logger.debug(query)

        users = await self.database.fetch_all(query)
        return users

    async def get_users_with_recent_user_message(self, since: datetime) -> list:
        """Devuelve usuarios que tienen al menos un mensaje de rol 'user' posterior a *since*.

        Permite al worker de lead follow-up omitir usuarios inactivos sin cargar
        todos los mensajes de la base de datos.
        """
        subq = (
            sqlalchemy.select(message_table.c.user_phone)
            .where(message_table.c.role == "user")
            .where(message_table.c.active.is_(True))
            .where(message_table.c.created_at >= since)
            .distinct()
            .subquery()
        )
        query = users_table.select().where(
            users_table.c.phone.in_(sqlalchemy.select(subq.c.user_phone))
        )
        if self.debug:
            logger.debug(query)
        return await self.database.fetch_all(query)

    def _normalize_user_data(self, **kwargs) -> dict:
        """Normaliza y filtra datos de usuario, eliminando None y espacios."""
        normalized: dict[str, object] = {}
        for key, value in kwargs.items():
            if value is not None:
                if isinstance(value, StrEnum):
                    normalized[key] = value.value
                    continue
                normalized[key] = value.strip() if isinstance(value, str) else value
        return normalized

    async def create_user(
        self, phone: str, permissions: str = "user", **kwargs
    ) -> bool:
        data = {
            "phone": phone,
            "permissions": permissions,
            "conversation_state": INITIAL_CONVERSATION_STATE.value,
        }
        data.update(self._normalize_user_data(**kwargs))
        ok = await self._create_user_with_data(phone, data)
        return ok

    async def _create_user_with_data(self, phone: str, data: dict) -> bool:
        data["phone"] = phone
        query = users_table.insert().values(data)
        if self.debug:
            logger.debug(query)

        try:
            await self.database.execute(query)
        except asyncpg.exceptions.UniqueViolationError:  # llave duplicada
            logger.warning(f"create_user: {phone} already exists in the database")
            return False

        logger.debug(f"{phone} created in the database")
        return True

    async def _update_user_data(self, phone: str, data: dict) -> bool:
        data["updated_at"] = sqlalchemy.func.now()
        query = users_table.update().where(users_table.c.phone == phone).values(**data)
        if self.debug:
            logger.debug(query)

        try:
            await self.database.execute(query)
            logger.debug(f"{phone} updated in the database")
            return True
        except Exception as exc:
            logger.error(exc)
            return False

    async def update_user(self, phone: str, **kwargs) -> bool:
        update_data = self._normalize_user_data(**kwargs)

        if not update_data:
            logger.warning(f"update_user: invalid data for update {phone}")
            return False

        return await self._update_user_data(phone, update_data)

    async def create_or_update_user(
        self, phone: str, permissions: str = "user", **kwargs
    ) -> bool:
        created = await self.create_user(phone, permissions=permissions, **kwargs)
        if not created:
            return await self.update_user(phone, **kwargs)
        return True

    async def create_or_update_user_with_data(self, phone: str, data: dict) -> bool:
        created = await self._create_user_with_data(phone, data)
        if not created:
            return await self._update_user_data(phone, data)
        return True

    async def create_message(
        self, phone: str, role: str, message: str, tools_used: list[str] | None = None
    ):
        if not await self.get_user(phone):
            await self.create_user(phone)

        data = {
            "user_phone": phone,
            "role": role,
            "message": message,
            "active": True,
        }
        if tools_used is not None:
            data["tools_used"] = json.dumps(tools_used)

        query = message_table.insert().values(data)
        if self.debug:
            logger.debug(query)

        await self.database.execute(query)
        if role == "user":
            await self.update_last_interaction(phone)

    async def update_last_interaction(
        self,
        phone: str,
        interacted_at: datetime | None = None,
    ) -> bool:
        return await self._update_user_data(
            phone,
            {
                "last_interaction": interacted_at
                or datetime.now(UTC).replace(tzinfo=None)
            },
        )

    async def get_users_with_active_conversations(self) -> list:
        subq = (
            sqlalchemy.select(message_table.c.user_phone)
            .where(message_table.c.active.is_(True))
            .distinct()
            .subquery()
        )
        query = users_table.select().where(
            users_table.c.phone.in_(sqlalchemy.select(subq.c.user_phone))
        )
        if self.debug:
            logger.debug(query)
        return await self.database.fetch_all(query)

    async def get_user_conversation_state(self, phone: str) -> ConversationState:
        user = await self.get_user(phone)
        if user is None:
            return INITIAL_CONVERSATION_STATE

        state_value = getattr(user, "conversation_state", None)
        if not state_value:
            return INITIAL_CONVERSATION_STATE
        return ConversationState(state_value)

    async def update_conversation_state(
        self,
        phone: str,
        state: ConversationState,
    ) -> bool:
        return await self.update_user(phone, conversation_state=state)

    async def update_follow_up_count(self, phone: str, follow_up_count: int) -> bool:
        return await self.update_user(phone, follow_up_count=follow_up_count)

    async def update_phase_2_answers(
        self,
        phone: str,
        answers: dict[str, str | None],
    ) -> bool:
        return await self.update_user(phone, **answers)

    async def get_demo_by_phone(self, phone: str):
        query = demos_table.select().where(demos_table.c.user_phone == phone)
        if self.debug:
            logger.debug(query)
        return await self.database.fetch_one(query)

    async def upsert_demo(
        self,
        demo: DemoRecord,
    ) -> bool:
        if not await self.get_user(demo.user_phone):
            await self.create_user(demo.user_phone)

        existing_demo = await self.get_demo_by_phone(demo.user_phone)
        values = {
            "user_phone": demo.user_phone,
            "title": demo.title,
            "duration_minutes": demo.duration_minutes,
            "description": demo.description,
            "scheduled_at": demo.scheduled_at,
            "google_calendar_event_id": demo.google_calendar_event_id,
            "upcoming_reminder_sent_at": demo.upcoming_reminder_sent_at,
        }

        if existing_demo is None:
            query = demos_table.insert().values(values)
        else:
            query = (
                demos_table.update()
                .where(demos_table.c.user_phone == demo.user_phone)
                .values(**values, updated_at=sqlalchemy.func.now())
            )

        if self.debug:
            logger.debug(query)

        await self.database.execute(query)
        return True

    async def mark_demo_reminder_sent(
        self,
        phone: str,
        sent_at: datetime | None = None,
    ) -> bool:
        query = (
            demos_table.update()
            .where(demos_table.c.user_phone == phone)
            .values(
                upcoming_reminder_sent_at=sent_at
                or datetime.now(UTC).replace(tzinfo=None),
                updated_at=sqlalchemy.func.now(),
            )
        )
        if self.debug:
            logger.debug(query)
        await self.database.execute(query)
        return True

    async def delete_demo_by_phone(self, phone: str) -> bool:
        query = demos_table.delete().where(demos_table.c.user_phone == phone)
        if self.debug:
            logger.debug(query)
        await self.database.execute(query)
        return True

    async def has_message(
        self,
        phone: str,
        role: str | None = None,
        message: str | None = None,
        active_only: bool = True,
    ) -> bool:
        query = message_table.select().where(message_table.c.user_phone == phone)
        if active_only:
            query = query.where(message_table.c.active.is_(True))
        if role is not None:
            query = query.where(message_table.c.role == role)
        if message is not None:
            query = query.where(message_table.c.message == message)
        query = query.limit(1)
        if self.debug:
            logger.debug(query)
        row = await self.database.fetch_one(query)
        return row is not None

    async def ensure_system_message(self, phone: str, message: str) -> None:
        exists = await self.has_message(phone=phone, role="system", message=message)
        if exists:
            return
        await self.create_message(phone=phone, role="system", message=message)

    async def deactivate_system_message(self, phone: str, message: str) -> None:
        query = (
            message_table.update()
            .where(message_table.c.user_phone == phone)
            .where(message_table.c.role == "system")
            .where(message_table.c.message == message)
            .where(message_table.c.active.is_(True))
            .values(active=False)
        )
        if self.debug:
            logger.debug(query)
        await self.database.execute(query)

    async def reset_chat(self, phone: str):
        logger.warning(f"Logically deactivating chats from {phone}")
        user = await self.get_user(phone)
        if not user:
            return f"reset_chat: {phone} no existe"

        query = (
            message_table.update()
            .where(message_table.c.user_phone == phone)
            .where(message_table.c.active.is_(True))
            .values(active=False)
        )
        if self.debug:
            logger.debug(query)

        await self.database.execute(query)

    async def get_recent_messages(self, phone: str, hours: int = 24) -> list:
        """Return all messages for *phone* created within the last *hours* hours."""
        since: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            hours=hours
        )
        query = (
            message_table.select()
            .where(message_table.c.user_phone == phone)
            .where(message_table.c.active.is_(True))
            .where(message_table.c.created_at >= since)
            .order_by(message_table.c.created_at.asc())
        )
        if self.debug:
            logger.debug(query)
        return await self.database.fetch_all(query)

    async def get_last_user_message(self, phone: str):
        """Return the most recent message sent by the user (role='user').

        Used to verify the META WhatsApp 24-hour free-messaging window.
        """
        query = (
            message_table.select()
            .where(message_table.c.user_phone == phone)
            .where(message_table.c.role == "user")
            .where(message_table.c.active.is_(True))
            .order_by(message_table.c.created_at.desc())
            .limit(1)
        )
        if self.debug:
            logger.debug(query)
        return await self.database.fetch_one(query)

    async def get_pydantic_ai_history(
        self, phone: str, hours: int = 24
    ) -> list[ModelMessage]:
        """Return the last *hours* hours of conversation as PydanticAI ModelMessage objects.

        Reconstructs ModelRequest/ModelResponse pairs from the stored text rows so
        the agent can continue the conversation with full context.
        """
        rows = await self.get_recent_messages(phone, hours=hours)
        history: list[ModelMessage] = []
        for row in rows:
            role: str = row.role  # type: ignore[attr-defined]
            raw: str = row.message  # type: ignore[attr-defined]
            content = raw.removeprefix("Usuario - ").removeprefix("Bot - ")
            if role == "user":
                history.append(ModelRequest(parts=[UserPromptPart(content=content)]))  # type: ignore
            elif role == "assistant":
                history.append(
                    ModelResponse(
                        parts=[TextPart(content=content)], model_name="restored"
                    )
                )
            elif role == "system":
                history.append(ModelRequest(parts=[SystemPromptPart(content=content)]))
        logger.debug(
            "Loaded %d history messages for %s (last %dh)", len(history), phone, hours
        )
        return history

    async def get_messages(self, phone: str):
        query = (
            message_table.select()
            .where(message_table.c.user_phone == phone)
            .where(message_table.c.active.is_(True))
            .order_by(message_table.c.created_at.asc())
        )
        if self.debug:
            logger.debug(query)

        return await self.database.fetch_all(query)

    async def get_all_messages(self, phone: str):
        query = (
            message_table.select()
            .where(message_table.c.user_phone == phone)
            .order_by(message_table.c.created_at.asc())
        )
        if self.debug:
            logger.debug(query)

        return await self.database.fetch_all(query)

    async def get_chat(self, phone: str) -> list[dict]:
        messages_obj = await self.get_messages(phone)
        chat = []
        for msg in messages_obj:
            message_dict = {"role": msg.role, "content": msg.message}  # type: ignore
            if msg.tools_used:  # type: ignore
                message_dict["tools_used"] = json.loads(msg.tools_used)  # type: ignore
            chat.append(message_dict)
        return chat

    async def get_chat_str(self, phone: str) -> str:
        messages = await self.get_chat(phone)
        return json.dumps(messages)


database = init_db()
services = Services(database)


if __name__ == "__main__":
    import asyncio

    async def test():
        await database.connect()
        phone = "+53 12345678"
        user = await services.get_user(phone)
        print("User:", user)
        await database.disconnect()

    asyncio.run(test())

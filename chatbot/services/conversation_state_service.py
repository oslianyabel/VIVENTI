from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from chatbot.db.services import Services, services
from chatbot.domain.conversation_states import ConversationState, can_transition

logger = logging.getLogger(__name__)

TransitionHook = Callable[[str, ConversationState, ConversationState], Awaitable[None]]


class InvalidConversationStateTransitionError(ValueError):
    def __init__(
        self,
        phone: str,
        source_state: ConversationState,
        target_state: ConversationState,
    ) -> None:
        self.phone = phone
        self.source_state = source_state
        self.target_state = target_state
        message = (
            "Invalid conversation state transition for "
            f"{phone}: {source_state.value} -> {target_state.value}"
        )
        super().__init__(message)


class ConversationStateService:
    def __init__(self, db_services: Services) -> None:
        self._db_services = db_services
        self._state_cache: dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()
        self._after_transition_hooks: list[TransitionHook] = []
        self._register_default_hooks()

    async def preload_active_users(self) -> None:
        async with self._lock:
            active_users = await self._db_services.get_users_with_active_conversations()
            self._state_cache = {
                user.phone: ConversationState(user.conversation_state)
                for user in active_users
            }

    def _register_default_hooks(self) -> None:
        """Register built-in post-transition hooks."""
        self.register_after_transition_hook(self._sync_google_sheets_hook)

    @staticmethod
    async def _sync_google_sheets_hook(
        phone: str,
        _source: ConversationState,
        target: ConversationState,
    ) -> None:
        """Trigger Google Sheets sync as a background task on every state change."""

        async def _do_sync() -> None:
            try:
                from chatbot.services.google_sheets_sync import sync_user_to_sheets

                await sync_user_to_sheets(phone)
            except Exception as exc:
                logger.error(
                    "[sheets_hook] Failed to sync phone=%s to Sheets: %s",
                    phone,
                    exc,
                )

        asyncio.create_task(_do_sync())

    def register_after_transition_hook(self, hook: TransitionHook) -> None:
        self._after_transition_hooks.append(hook)

    def invalidate_cache(self, phone: str) -> None:
        """Remove a phone entry from the state cache so the next read hits the DB."""
        self._state_cache.pop(phone, None)

    async def get_state(self, phone: str) -> ConversationState:
        cached_state = self._state_cache.get(phone)
        if cached_state is not None:
            return cached_state

        state = await self._db_services.get_user_conversation_state(phone)
        async with self._lock:
            self._state_cache[phone] = state
        return state

    async def transition(
        self,
        phone: str,
        source_state: ConversationState,
        target_state: ConversationState,
    ) -> ConversationState:
        async with self._lock:
            current_state = self._state_cache.get(phone)
            if current_state is None:
                current_state = await self._db_services.get_user_conversation_state(
                    phone
                )

            if current_state != source_state or not can_transition(
                source_state,
                target_state,
            ):
                raise InvalidConversationStateTransitionError(
                    phone=phone,
                    source_state=current_state,
                    target_state=target_state,
                )

            updated = await self._db_services.update_conversation_state(
                phone, target_state
            )
            if not updated:
                raise RuntimeError(f"Could not persist conversation state for {phone}")

            self._state_cache[phone] = target_state

        for hook in self._after_transition_hooks:
            await hook(phone, source_state, target_state)

        return target_state

    async def phase_1_to_phase_2(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.PHASE_1,
            target_state=ConversationState.PHASE_2,
        )

    async def phase_2_to_phase_3(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.PHASE_2,
            target_state=ConversationState.PHASE_3,
        )

    async def phase_2_to_discard(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.PHASE_2,
            target_state=ConversationState.DISCARD,
        )

    async def phase_3_to_completed(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.PHASE_3,
            target_state=ConversationState.COMPLETED,
        )

    async def phase_3_to_lost(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.PHASE_3,
            target_state=ConversationState.LOST,
        )

    async def completed_to_lost(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.COMPLETED,
            target_state=ConversationState.LOST,
        )

    async def lost_to_completed(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.LOST,
            target_state=ConversationState.COMPLETED,
        )

    async def discard_to_phase_3(self, phone: str) -> ConversationState:
        return await self.transition(
            phone=phone,
            source_state=ConversationState.DISCARD,
            target_state=ConversationState.PHASE_3,
        )


conversation_state_service = ConversationStateService(services)

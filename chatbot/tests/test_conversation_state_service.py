# uv run python -m pytest -s chatbot/tests/test_conversation_state_service.py

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from chatbot.db.schema import init_db
from chatbot.db.services import Services
from chatbot.domain.conversation_states import ConversationState
from chatbot.services.conversation_state_service import (
    ConversationStateService,
    InvalidConversationStateTransitionError,
)

TEST_PHONE = "987654321"


@pytest.fixture()
async def db():
    database = init_db()
    try:
        await database.connect()
    except OSError as exc:
        pytest.skip(f"PostgreSQL is not available for integration tests: {exc}")

    yield database

    if database.is_connected:
        await database.disconnect()


@pytest.fixture()
def services(db) -> Services:
    return Services(database=db)


@pytest.fixture()
def state_service(services: Services) -> ConversationStateService:
    return ConversationStateService(db_services=services)


@pytest.fixture(autouse=True)
async def clean_test_data(services: Services, db) -> AsyncGenerator[None, None]:
    user = await services.get_user(TEST_PHONE)
    if user:
        from chatbot.db.schema import demos_table, message_table, users_table

        await db.execute(
            demos_table.delete().where(demos_table.c.user_phone == TEST_PHONE)
        )
        await db.execute(
            message_table.delete().where(message_table.c.user_phone == TEST_PHONE)
        )
        await db.execute(users_table.delete().where(users_table.c.phone == TEST_PHONE))
    yield
    user = await services.get_user(TEST_PHONE)
    if user:
        from chatbot.db.schema import demos_table, message_table, users_table

        await db.execute(
            demos_table.delete().where(demos_table.c.user_phone == TEST_PHONE)
        )
        await db.execute(
            message_table.delete().where(message_table.c.user_phone == TEST_PHONE)
        )
        await db.execute(users_table.delete().where(users_table.c.phone == TEST_PHONE))


@pytest.mark.anyio
async def test_preload_active_users_loads_state_cache(
    services: Services,
    state_service: ConversationStateService,
) -> None:
    await services.create_user(TEST_PHONE)
    await services.update_conversation_state(TEST_PHONE, ConversationState.PHASE_2)
    await services.create_message(TEST_PHONE, "user", "Hola")

    await state_service.preload_active_users()
    state = await state_service.get_state(TEST_PHONE)

    print(f"\n  preloaded state -> {state}")
    assert state == ConversationState.PHASE_2


@pytest.mark.anyio
async def test_phase_1_to_phase_2_updates_cache_and_db(
    services: Services,
    state_service: ConversationStateService,
) -> None:
    await services.create_user(TEST_PHONE)

    state = await state_service.phase_1_to_phase_2(TEST_PHONE)
    persisted_state = await services.get_user_conversation_state(TEST_PHONE)

    print(f"\n  transition state -> {state}")
    assert state == ConversationState.PHASE_2
    assert persisted_state == ConversationState.PHASE_2


@pytest.mark.anyio
async def test_invalid_transition_raises_specific_error(
    services: Services,
    state_service: ConversationStateService,
) -> None:
    await services.create_user(TEST_PHONE)

    with pytest.raises(InvalidConversationStateTransitionError) as exc_info:
        await state_service.phase_3_to_completed(TEST_PHONE)

    print(f"\n  invalid transition -> {exc_info.value}")
    assert exc_info.value.source_state == ConversationState.PHASE_1
    assert exc_info.value.target_state == ConversationState.COMPLETED


@pytest.mark.anyio
async def test_discard_to_phase_3_allows_requalification(
    services: Services,
    state_service: ConversationStateService,
) -> None:
    await services.create_user(TEST_PHONE)
    await services.update_conversation_state(TEST_PHONE, ConversationState.PHASE_2)
    await state_service.phase_2_to_discard(TEST_PHONE)

    state = await state_service.discard_to_phase_3(TEST_PHONE)
    persisted_state = await services.get_user_conversation_state(TEST_PHONE)

    print(f"\n  requalified state -> {state}")
    assert state == ConversationState.PHASE_3
    assert persisted_state == ConversationState.PHASE_3

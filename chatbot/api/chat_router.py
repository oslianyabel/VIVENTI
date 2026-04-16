import logging

from fastapi import APIRouter, Depends, HTTPException

from chatbot.api.utils.models import (
    Messages,
    SheetsRowResponse,
    UserDetailResponse,
    UserResponse,
)
from chatbot.api.utils.security import get_api_key
from chatbot.db.services import services
from chatbot.services.google_sheets_service import get_row_by_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", dependencies=[Depends(get_api_key)])


@router.get("/users", response_model=list[UserResponse])
async def get_all_users():
    logger.info("Fetching all users")
    return await services.get_all_users()


@router.get("/users/{phone}", response_model=UserDetailResponse)
async def get_user(phone: str):
    logger.info(f"Fetching user with phone: {phone}")
    user = await services.get_user(phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = dict(user._mapping)
    demo = await services.get_demo_by_phone(phone)
    if demo:
        data["demo"] = dict(demo._mapping)
    return data


@router.get("/messages/{phone}", response_model=list[Messages])
async def get_messages(phone: str):
    logger.info(f"Fetching messages for phone: {phone}")
    return await services.get_messages(phone)


@router.get("/sheets/{phone}", response_model=SheetsRowResponse)
async def get_sheets_row(phone: str):
    logger.info(f"Fetching sheets row for phone: {phone}")
    row = await get_row_by_phone(phone)
    if not row:
        raise HTTPException(status_code=404, detail="Row not found in Google Sheets")
    return row

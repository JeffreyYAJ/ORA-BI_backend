from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/pipelines/{pipeline_id}/chat", tags=["chat"])


@router.get("", response_model=list[ChatMessageRead])
async def list_chat(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> list[ChatMessageRead]:
    return await chat_service.list_chat_messages(db, pipeline_id)


@router.post("", response_model=ChatResponse)
async def post_chat(
    pipeline_id: UUID, data: ChatMessageCreate, db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    return await chat_service.handle_chat_message(db, pipeline_id, data.content)

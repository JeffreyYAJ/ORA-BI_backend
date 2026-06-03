from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user_question import UserQuestion
from app.schemas.user_question import UserQuestionAnswerRequest, UserQuestionRead
from app.services import user_input_service
from app.services.pipeline_service import get_pipeline_or_404

router = APIRouter(prefix="/pipelines/{pipeline_id}/questions", tags=["questions"])


@router.get("", response_model=list[UserQuestionRead])
async def list_questions(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
    run_id: UUID | None = Query(None),
    pending_only: bool = Query(True),
) -> list[UserQuestionRead]:
    if pending_only:
        return await user_input_service.list_pending_questions(db, pipeline_id, run_id=run_id)
    await get_pipeline_or_404(db, pipeline_id)
    q = select(UserQuestion).where(UserQuestion.pipeline_id == pipeline_id)
    if run_id:
        q = q.where(UserQuestion.run_id == run_id)
    result = await db.execute(q.order_by(UserQuestion.created_at.desc()))
    return [UserQuestionRead.model_validate(row) for row in result.scalars().all()]


@router.post("/{question_id}/answer", response_model=UserQuestionRead)
async def answer_question_endpoint(
    pipeline_id: UUID,
    question_id: UUID,
    body: UserQuestionAnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> UserQuestionRead:
    answered = await user_input_service.answer_question(db, pipeline_id, question_id, body.answer)
    if answered.run_id:
        from app.services.execution_service import continue_run_after_answer

        await continue_run_after_answer(db, pipeline_id, answered.run_id)
    return answered

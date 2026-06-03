from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PipelineRunEventType, PipelineRunStatus
from app.schemas.guardian import GuardianApprovalRead
from app.schemas.user_question import UserQuestionRead


class PipelineRunEventRead(BaseModel):
    id: UUID
    run_id: UUID
    pipeline_id: UUID
    event_type: PipelineRunEventType
    message_md: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineRunRead(BaseModel):
    id: UUID
    pipeline_id: UUID
    status: PipelineRunStatus
    current_node_id: UUID | None
    context: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    events: list[PipelineRunEventRead] = Field(default_factory=list)
    pending_approvals: list[GuardianApprovalRead] = Field(default_factory=list)
    pending_questions: list[UserQuestionRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PipelineRunStartResponse(BaseModel):
    run: PipelineRunRead
    message: str


class GuardianQuestionAnswer(BaseModel):
    question_id: str = Field(description="ID de l'événement GUARDIAN_QUESTION")
    answer: str = Field(min_length=1)

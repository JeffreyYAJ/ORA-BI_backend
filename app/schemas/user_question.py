from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AgentRole, UserQuestionStatus, WorkflowPhase


class UserQuestionRead(BaseModel):
    id: UUID
    pipeline_id: UUID
    run_id: UUID | None
    agent_task_id: UUID | None
    node_id: UUID | None
    agent_role: AgentRole
    phase: WorkflowPhase
    question_text: str
    context_snapshot: dict[str, Any]
    choices: list[str]
    status: UserQuestionStatus
    answer_text: str | None
    created_at: datetime
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class UserQuestionAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)

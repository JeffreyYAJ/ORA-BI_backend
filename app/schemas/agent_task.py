from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AgentRole, AgentTaskStatus


class AgentTaskCreate(BaseModel):
    agent_role: AgentRole
    instruction: str
    node_id: UUID | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)


class AgentTaskRead(BaseModel):
    id: UUID
    pipeline_id: UUID
    node_id: UUID | None
    agent_role: AgentRole
    instruction: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    status: AgentTaskStatus
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}

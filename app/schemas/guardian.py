from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ApprovalStatus, GuardianOperationType


class GuardianApprovalRead(BaseModel):
    id: UUID
    pipeline_id: UUID
    run_id: UUID | None
    node_id: UUID | None
    agent_task_id: UUID | None
    operation_type: GuardianOperationType
    title: str
    description: str
    risk_level: str
    status: ApprovalStatus
    masked_preview: dict[str, Any]
    pii_findings: list[dict[str, Any]]
    pending_action: dict[str, Any]
    user_comment: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalDecideRequest(BaseModel):
    approved: bool
    comment: str | None = None


class NodeUpdateBlockedResponse(BaseModel):
    detail: str
    approval_required: bool = True
    approval: GuardianApprovalRead

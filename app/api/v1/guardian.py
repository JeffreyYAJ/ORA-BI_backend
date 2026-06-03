from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.enums import ApprovalStatus
from app.schemas.guardian import ApprovalDecideRequest, GuardianApprovalRead
from app.services import guardian_service

router = APIRouter(prefix="/pipelines/{pipeline_id}/approvals", tags=["guardian"])


@router.get("", response_model=list[GuardianApprovalRead])
async def list_approvals(
    pipeline_id: UUID,
    db: AsyncSession = Depends(get_db),
    status: ApprovalStatus | None = Query(None),
) -> list[GuardianApprovalRead]:
    return await guardian_service.list_approvals(db, pipeline_id, status=status)


@router.post("/{approval_id}/decide", response_model=GuardianApprovalRead)
async def decide_approval(
    pipeline_id: UUID,
    approval_id: UUID,
    body: ApprovalDecideRequest,
    db: AsyncSession = Depends(get_db),
) -> GuardianApprovalRead:
    return await guardian_service.decide_approval(
        db, pipeline_id, approval_id, body.approved, body.comment
    )

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ApprovalStatus, GuardianOperationType


class GuardianApproval(Base):
    __tablename__ = "guardian_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )
    operation_type: Mapped[GuardianOperationType] = mapped_column(
        Enum(GuardianOperationType, name="guardian_operation_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="HIGH")
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status", values_callable=lambda x: [e.value for e in x]),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    masked_preview: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    pii_findings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    pending_action: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pipeline = relationship("Pipeline", back_populates="guardian_approvals")
    run = relationship("PipelineRun", back_populates="approvals")

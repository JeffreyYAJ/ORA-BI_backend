import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PipelineRunStatus


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        Enum(PipelineRunStatus, name="pipeline_run_status", values_callable=lambda x: [e.value for e in x]),
        default=PipelineRunStatus.PENDING,
        nullable=False,
    )
    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pipeline = relationship("Pipeline", back_populates="pipeline_runs")
    events = relationship("PipelineRunEvent", back_populates="run", cascade="all, delete-orphan")
    approvals = relationship("GuardianApproval", back_populates="run", cascade="all, delete-orphan")

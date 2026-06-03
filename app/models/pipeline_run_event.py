import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PipelineRunEventType


class PipelineRunEvent(Base):
    __tablename__ = "pipeline_run_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[PipelineRunEventType] = mapped_column(
        Enum(PipelineRunEventType, name="pipeline_run_event_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    message_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run = relationship("PipelineRun", back_populates="events")

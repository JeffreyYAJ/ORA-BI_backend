import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PipelineStatus


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status", values_callable=lambda x: [e.value for e in x]),
        default=PipelineStatus.DRAFT,
        nullable=False,
    )
    architecture_design: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    nodes = relationship("Node", back_populates="pipeline", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="pipeline", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="pipeline", cascade="all, delete-orphan")
    agent_tasks = relationship("AgentTask", back_populates="pipeline", cascade="all, delete-orphan")

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AgentRole, UserQuestionStatus, WorkflowPhase


class UserQuestion(Base):
    __tablename__ = "user_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    agent_role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    phase: Mapped[WorkflowPhase] = mapped_column(
        Enum(WorkflowPhase, name="workflow_phase", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    choices: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[UserQuestionStatus] = mapped_column(
        Enum(UserQuestionStatus, name="user_question_status", values_callable=lambda x: [e.value for e in x]),
        default=UserQuestionStatus.PENDING,
        nullable=False,
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pipeline = relationship("Pipeline", back_populates="user_questions")

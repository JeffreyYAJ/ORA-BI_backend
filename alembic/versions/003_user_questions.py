"""user questions for contextual agent input

Revision ID: 003
Revises: 002
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE pipeline_run_event_type ADD VALUE IF NOT EXISTS 'USER_QUESTION'")

    op.create_table(
        "user_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "agent_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "agent_role",
            postgresql.ENUM(
                "MASTER",
                "PROFILER",
                "ENGINEER",
                "DEBUGGER",
                "GUARDIAN",
                "QA",
                "AUDITOR",
                name="agent_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "phase",
            sa.Enum("INITIAL_STUDY", "AGENT_TASK", "NODE_EXECUTION", "CHAT", name="workflow_phase"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("choices", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ANSWERED", "CANCELLED", name="user_question_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_questions_pipeline_id", "user_questions", ["pipeline_id"])
    op.create_index("ix_user_questions_run_id", "user_questions", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_user_questions_run_id", table_name="user_questions")
    op.drop_index("ix_user_questions_pipeline_id", table_name="user_questions")
    op.drop_table("user_questions")
    op.execute("DROP TYPE IF EXISTS user_question_status")
    op.execute("DROP TYPE IF EXISTS workflow_phase")

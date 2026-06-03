"""guardian execution and approvals

Revision ID: 002
Revises: 001
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE chat_sender ADD VALUE IF NOT EXISTS 'GUARDIAN_AGENT'")

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "AWAITING_APPROVAL",
                "AWAITING_USER_INPUT",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="pipeline_run_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("current_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pipeline_runs_pipeline_id", "pipeline_runs", ["pipeline_id"])

    op.create_table(
        "guardian_approvals",
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
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "agent_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "operation_type",
            sa.Enum(
                "DELETE_COLUMN",
                "EXPORT_DATA",
                "SINK_WRITE",
                "BULK_TRANSFORM",
                "PII_EXPOSURE",
                "PIPELINE_RUN",
                "CUSTOM",
                name="guardian_operation_type",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(32), nullable=False, server_default="HIGH"),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="approval_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("masked_preview", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("pii_findings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("pending_action", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("user_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guardian_approvals_pipeline_id", "guardian_approvals", ["pipeline_id"])
    op.create_index("ix_guardian_approvals_run_id", "guardian_approvals", ["run_id"])

    op.create_table(
        "pipeline_run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "RUN_STARTED",
                "STEP_STARTED",
                "STEP_COMPLETED",
                "PII_DETECTED",
                "APPROVAL_REQUIRED",
                "GUARDIAN_QUESTION",
                "RUN_PAUSED",
                "RUN_RESUMED",
                "RUN_COMPLETED",
                "RUN_FAILED",
                name="pipeline_run_event_type",
            ),
            nullable=False,
        ),
        sa.Column("message_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pipeline_run_events_run_id", "pipeline_run_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_events_run_id", table_name="pipeline_run_events")
    op.drop_table("pipeline_run_events")
    op.drop_index("ix_guardian_approvals_run_id", table_name="guardian_approvals")
    op.drop_index("ix_guardian_approvals_pipeline_id", table_name="guardian_approvals")
    op.drop_table("guardian_approvals")
    op.drop_index("ix_pipeline_runs_pipeline_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.execute("DROP TYPE IF EXISTS pipeline_run_event_type")
    op.execute("DROP TYPE IF EXISTS approval_status")
    op.execute("DROP TYPE IF EXISTS guardian_operation_type")
    op.execute("DROP TYPE IF EXISTS pipeline_run_status")

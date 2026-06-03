"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ACTIVE", "ARCHIVED", name="pipeline_status"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("architecture_design", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Enum("SOURCE", "TRANSFORM", "SINK", name="node_type"), nullable=False),
        sa.Column(
            "subtype",
            sa.Enum(
                "csv", "json", "python_script", "sql_query", "postgres_sink", "sqlite", "generic",
                name="node_subtype",
            ),
            nullable=False,
            server_default="generic",
        ),
        sa.Column("label", sa.String(255), nullable=False, server_default="Node"),
        sa.Column("position_x", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position_y", sa.Float(), nullable=False, server_default="0"),
        sa.Column("internal_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum("IDLE", "PENDING", "VALID", "ERROR", name="node_status"),
            nullable=False,
            server_default="IDLE",
        ),
    )
    op.create_index("ix_nodes_pipeline_id", "nodes", ["pipeline_id"])

    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_edges_pipeline_id", "edges", ["pipeline_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.Enum("USER", "MASTER_AGENT", name="chat_sender"), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_pipeline_id", "chat_messages", ["pipeline_id"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "agent_role",
            sa.Enum(
                "MASTER", "PROFILER", "ENGINEER", "DEBUGGER", "GUARDIAN", "QA", "AUDITOR",
                name="agent_role",
            ),
            nullable=False,
        ),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="agent_task_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_tasks_pipeline_id", "agent_tasks", ["pipeline_id"])


def downgrade() -> None:
    op.drop_table("agent_tasks")
    op.drop_table("chat_messages")
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("pipelines")
    op.execute("DROP TYPE IF EXISTS agent_task_status")
    op.execute("DROP TYPE IF EXISTS agent_role")
    op.execute("DROP TYPE IF EXISTS chat_sender")
    op.execute("DROP TYPE IF EXISTS node_status")
    op.execute("DROP TYPE IF EXISTS node_subtype")
    op.execute("DROP TYPE IF EXISTS node_type")
    op.execute("DROP TYPE IF EXISTS pipeline_status")

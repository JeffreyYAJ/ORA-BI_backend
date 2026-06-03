import uuid

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NodeStatus, NodeSubtype, NodeType


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="node_type", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    subtype: Mapped[NodeSubtype] = mapped_column(
        Enum(NodeSubtype, name="node_subtype", values_callable=lambda x: [e.value for e in x]),
        default=NodeSubtype.GENERIC,
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Node")
    position_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    internal_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[NodeStatus] = mapped_column(
        Enum(NodeStatus, name="node_status", values_callable=lambda x: [e.value for e in x]),
        default=NodeStatus.IDLE,
        nullable=False,
    )

    pipeline = relationship("Pipeline", back_populates="nodes")
    outgoing_edges = relationship(
        "Edge", foreign_keys="Edge.source_node_id", back_populates="source_node", cascade="all, delete-orphan"
    )
    incoming_edges = relationship(
        "Edge", foreign_keys="Edge.target_node_id", back_populates="target_node", cascade="all, delete-orphan"
    )

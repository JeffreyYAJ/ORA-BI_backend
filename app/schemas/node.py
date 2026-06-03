from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import NodeStatus, NodeSubtype, NodeType


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class NodeCreate(BaseModel):
    type: NodeType
    subtype: NodeSubtype = NodeSubtype.GENERIC
    label: str = "Node"
    position: Position = Field(default_factory=Position)
    data: dict[str, Any] = Field(default_factory=dict)
    status: NodeStatus = NodeStatus.IDLE


class NodeUpdate(BaseModel):
    type: NodeType | None = None
    subtype: NodeSubtype | None = None
    label: str | None = None
    position: Position | None = None
    data: dict[str, Any] | None = None
    status: NodeStatus | None = None


class NodeRead(BaseModel):
    id: UUID
    type: NodeType
    subtype: NodeSubtype
    label: str
    position: Position
    data: dict[str, Any]
    status: NodeStatus

    model_config = {"from_attributes": True}

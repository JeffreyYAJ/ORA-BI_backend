from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PipelineStatus
from app.schemas.edge import EdgeRead
from app.schemas.node import NodeRead


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: PipelineStatus | None = None
    architecture_design: dict[str, Any] | None = None


class PipelineListItem(BaseModel):
    id: UUID
    name: str
    status: PipelineStatus
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineRead(BaseModel):
    id: UUID
    name: str
    status: PipelineStatus
    architecture_design: dict[str, Any] | None
    updated_at: datetime
    nodes: list[NodeRead]
    edges: list[EdgeRead]

    model_config = {"from_attributes": True}

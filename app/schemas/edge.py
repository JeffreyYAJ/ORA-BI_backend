from uuid import UUID

from pydantic import BaseModel


class EdgeCreate(BaseModel):
    source_node_id: UUID
    target_node_id: UUID


class EdgeRead(BaseModel):
    id: UUID
    source: UUID
    target: UUID

    model_config = {"from_attributes": True}

from uuid import UUID

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.node import NodeCreate, NodeRead, NodeUpdate
from app.services import pipeline_service

router = APIRouter(prefix="/pipelines/{pipeline_id}/nodes", tags=["nodes"])


@router.post("", response_model=NodeRead, status_code=201)
async def create_node(
    pipeline_id: UUID, data: NodeCreate, db: AsyncSession = Depends(get_db)
) -> NodeRead:
    return await pipeline_service.create_node(db, pipeline_id, data)


@router.patch("/{node_id}", response_model=NodeRead)
async def update_node(
    pipeline_id: UUID, node_id: UUID, data: NodeUpdate, db: AsyncSession = Depends(get_db)
) -> NodeRead:
    return await pipeline_service.update_node(db, pipeline_id, node_id, data)


@router.delete("/{node_id}", status_code=204)
async def delete_node(pipeline_id: UUID, node_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await pipeline_service.delete_node(db, pipeline_id, node_id)

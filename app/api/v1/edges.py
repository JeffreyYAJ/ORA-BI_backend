from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.edge import EdgeCreate, EdgeRead
from app.services import pipeline_service

router = APIRouter(prefix="/pipelines/{pipeline_id}/edges", tags=["edges"])


@router.post("", response_model=EdgeRead, status_code=201)
async def create_edge(
    pipeline_id: UUID, data: EdgeCreate, db: AsyncSession = Depends(get_db)
) -> EdgeRead:
    return await pipeline_service.create_edge(db, pipeline_id, data)


@router.delete("/{edge_id}", status_code=204)
async def delete_edge(pipeline_id: UUID, edge_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await pipeline_service.delete_edge(db, pipeline_id, edge_id)

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.pipeline import PipelineCreate, PipelineListItem, PipelineRead, PipelineUpdate
from app.services import pipeline_service

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("", response_model=PipelineRead, status_code=201)
async def create_pipeline(data: PipelineCreate, db: AsyncSession = Depends(get_db)) -> PipelineRead:
    return await pipeline_service.create_pipeline(db, data)


@router.get("", response_model=list[PipelineListItem])
async def list_pipelines(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[PipelineListItem]:
    return await pipeline_service.list_pipelines(db, skip=skip, limit=limit)


@router.get("/{pipeline_id}", response_model=PipelineRead)
async def get_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> PipelineRead:
    return await pipeline_service.get_pipeline(db, pipeline_id)


@router.patch("/{pipeline_id}", response_model=PipelineRead)
async def update_pipeline(
    pipeline_id: UUID, data: PipelineUpdate, db: AsyncSession = Depends(get_db)
) -> PipelineRead:
    return await pipeline_service.update_pipeline(db, pipeline_id, data)


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await pipeline_service.delete_pipeline(db, pipeline_id)

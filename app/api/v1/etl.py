from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.etl import EtlExecuteRequest, EtlExecuteResponse, EtlIntrospectResponse
from app.services import data_source_service, etl_workflow_service

router = APIRouter(prefix="/pipelines/{pipeline_id}/etl", tags=["etl"])


@router.post("/introspect", response_model=EtlIntrospectResponse)
async def introspect_sources(
    pipeline_id: UUID, db: AsyncSession = Depends(get_db)
) -> EtlIntrospectResponse:
    profile = await data_source_service.introspect_pipeline_sources(db, pipeline_id)
    if not profile.get("primary_source"):
        raise HTTPException(
            status_code=422,
            detail="Aucune source PostgreSQL accessible. Vérifiez schema/table et la base (seed_demo_banking.sql).",
        )
    return EtlIntrospectResponse(
        live_data_profile=profile,
        message="Sources lues en ligne — profil disponible pour les agents et l'ETL.",
    )


@router.post("/execute", response_model=EtlExecuteResponse)
async def execute_etl(
    pipeline_id: UUID,
    body: EtlExecuteRequest,
    db: AsyncSession = Depends(get_db),
) -> EtlExecuteResponse:
    try:
        return await etl_workflow_service.execute_user_etl(db, pipeline_id, body.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/results")
async def get_etl_results(pipeline_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    result = await etl_workflow_service.get_last_etl_result(db, pipeline_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucun résultat ETL pour ce pipeline")
    return result

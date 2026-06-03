from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import ProgrammingError

from app.api.v1 import agent_tasks, chat, edges, etl, execution, guardian, nodes, pipelines, questions, ws
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="DataPipe API",
    description="Visual ETL backend for banking pipelines (ORA-BI)",
    version="0.1.0",
    lifespan=lifespan,
)

if settings.cors_allow_all:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

api_prefix = "/api/v1"
app.include_router(pipelines.router, prefix=api_prefix)
app.include_router(nodes.router, prefix=api_prefix)
app.include_router(edges.router, prefix=api_prefix)
app.include_router(chat.router, prefix=api_prefix)
app.include_router(execution.router, prefix=api_prefix)
app.include_router(guardian.router, prefix=api_prefix)
app.include_router(agent_tasks.router, prefix=api_prefix)
app.include_router(questions.router, prefix=api_prefix)
app.include_router(etl.router, prefix=api_prefix)
app.include_router(ws.router, prefix=api_prefix)


@app.exception_handler(ProgrammingError)
async def database_schema_error(_request: Request, exc: ProgrammingError) -> JSONResponse:
    message = str(getattr(exc, "orig", exc))
    if "does not exist" in message:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Schéma PostgreSQL incomplet (tables Gardien / exécution manquantes). "
                    "Exécutez : `./scripts/migrate.sh` ou `alembic upgrade head`"
                ),
            },
        )
    raise exc


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_configured": settings.llm_configured,
    }

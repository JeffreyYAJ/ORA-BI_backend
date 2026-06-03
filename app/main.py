from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, edges, nodes, pipelines, ws
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
app.include_router(ws.router, prefix=api_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

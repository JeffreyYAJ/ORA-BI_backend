from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.edge import Edge
from app.models.enums import PipelineStatus
from app.models.node import Node
from app.models.pipeline import Pipeline
from app.schemas.edge import EdgeCreate, EdgeRead
from app.schemas.node import NodeCreate, NodeRead, NodeUpdate, Position
from app.schemas.pipeline import PipelineCreate, PipelineListItem, PipelineRead, PipelineUpdate
from app.websocket.events import WsEvent, WsEventType
from app.websocket.manager import ws_manager


def node_to_read(node: Node) -> NodeRead:
    return NodeRead(
        id=node.id,
        type=node.type,
        subtype=node.subtype,
        label=node.label,
        position=Position(x=node.position_x, y=node.position_y),
        data=node.internal_data or {},
        status=node.status,
    )


def edge_to_read(edge: Edge) -> EdgeRead:
    return EdgeRead(id=edge.id, source=edge.source_node_id, target=edge.target_node_id)


def pipeline_to_read(pipeline: Pipeline) -> PipelineRead:
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        status=pipeline.status,
        architecture_design=pipeline.architecture_design,
        updated_at=pipeline.updated_at,
        nodes=[node_to_read(n) for n in pipeline.nodes],
        edges=[edge_to_read(e) for e in pipeline.edges],
    )


async def get_pipeline_or_404(db: AsyncSession, pipeline_id: UUID) -> Pipeline:
    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.nodes), selectinload(Pipeline.edges))
    )
    pipeline = result.scalar_one_or_none()
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


async def list_pipelines(db: AsyncSession, skip: int = 0, limit: int = 50) -> list[PipelineListItem]:
    result = await db.execute(
        select(Pipeline).order_by(Pipeline.updated_at.desc()).offset(skip).limit(limit)
    )
    return [PipelineListItem.model_validate(p) for p in result.scalars().all()]


async def create_pipeline(db: AsyncSession, data: PipelineCreate) -> PipelineRead:
    pipeline = Pipeline(name=data.name, status=PipelineStatus.DRAFT)
    db.add(pipeline)
    await db.flush()
    await db.refresh(pipeline, ["nodes", "edges"])
    read = pipeline_to_read(pipeline)
    await ws_manager.broadcast(
        pipeline.id,
        WsEvent(type=WsEventType.PIPELINE_UPDATED, pipeline_id=str(pipeline.id), payload=read.model_dump(mode="json")),
    )
    return read


async def get_pipeline(db: AsyncSession, pipeline_id: UUID) -> PipelineRead:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    return pipeline_to_read(pipeline)


async def update_pipeline(db: AsyncSession, pipeline_id: UUID, data: PipelineUpdate) -> PipelineRead:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    if data.name is not None:
        pipeline.name = data.name
    if data.status is not None:
        pipeline.status = data.status
    if data.architecture_design is not None:
        pipeline.architecture_design = data.architecture_design
    await db.flush()
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    read = pipeline_to_read(pipeline)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.PIPELINE_UPDATED, pipeline_id=str(pipeline_id), payload=read.model_dump(mode="json")),
    )
    return read


async def delete_pipeline(db: AsyncSession, pipeline_id: UUID) -> None:
    pipeline = await get_pipeline_or_404(db, pipeline_id)
    await db.delete(pipeline)


async def _get_node_in_pipeline(db: AsyncSession, pipeline_id: UUID, node_id: UUID) -> Node:
    result = await db.execute(select(Node).where(Node.id == node_id, Node.pipeline_id == pipeline_id))
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


async def create_node(db: AsyncSession, pipeline_id: UUID, data: NodeCreate) -> NodeRead:
    await get_pipeline_or_404(db, pipeline_id)
    node = Node(
        pipeline_id=pipeline_id,
        type=data.type,
        subtype=data.subtype,
        label=data.label,
        position_x=data.position.x,
        position_y=data.position.y,
        internal_data=data.data,
        status=data.status,
    )
    db.add(node)
    await db.flush()
    read = node_to_read(node)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.NODE_CREATED, pipeline_id=str(pipeline_id), payload=read.model_dump(mode="json")),
    )
    return read


async def update_node(db: AsyncSession, pipeline_id: UUID, node_id: UUID, data: NodeUpdate) -> NodeRead:
    node = await _get_node_in_pipeline(db, pipeline_id, node_id)
    if data.type is not None:
        node.type = data.type
    if data.subtype is not None:
        node.subtype = data.subtype
    if data.label is not None:
        node.label = data.label
    if data.position is not None:
        node.position_x = data.position.x
        node.position_y = data.position.y
    if data.data is not None:
        node.internal_data = data.data
    if data.status is not None:
        node.status = data.status
    await db.flush()
    read = node_to_read(node)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.NODE_UPDATED, pipeline_id=str(pipeline_id), payload=read.model_dump(mode="json")),
    )
    return read


async def delete_node(db: AsyncSession, pipeline_id: UUID, node_id: UUID) -> None:
    node = await _get_node_in_pipeline(db, pipeline_id, node_id)
    await db.delete(node)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.NODE_DELETED, pipeline_id=str(pipeline_id), payload={"id": str(node_id)}),
    )


async def create_edge(db: AsyncSession, pipeline_id: UUID, data: EdgeCreate) -> EdgeRead:
    await get_pipeline_or_404(db, pipeline_id)
    if data.source_node_id == data.target_node_id:
        raise HTTPException(status_code=400, detail="Source and target must differ")
    source = await _get_node_in_pipeline(db, pipeline_id, data.source_node_id)
    target = await _get_node_in_pipeline(db, pipeline_id, data.target_node_id)
    edge = Edge(
        pipeline_id=pipeline_id,
        source_node_id=source.id,
        target_node_id=target.id,
    )
    db.add(edge)
    await db.flush()
    read = edge_to_read(edge)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.EDGE_CREATED, pipeline_id=str(pipeline_id), payload=read.model_dump(mode="json")),
    )
    return read


async def delete_edge(db: AsyncSession, pipeline_id: UUID, edge_id: UUID) -> None:
    result = await db.execute(select(Edge).where(Edge.id == edge_id, Edge.pipeline_id == pipeline_id))
    edge = result.scalar_one_or_none()
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    edge_id_str = str(edge.id)
    await db.delete(edge)
    await ws_manager.broadcast(
        pipeline_id,
        WsEvent(type=WsEventType.EDGE_DELETED, pipeline_id=str(pipeline_id), payload={"id": edge_id_str}),
    )

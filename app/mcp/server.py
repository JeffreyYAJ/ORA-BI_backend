"""FastMCP server exposing Master Agent tools for IDE integration."""

from uuid import UUID

from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.enums import AgentRole
from app.models.pipeline import Pipeline
from app.services.agent_task_service import create_agent_task
from app.services.pipeline_service import pipeline_to_read

mcp = FastMCP("DataPipe Master Agent")


@mcp.tool()
async def get_pipeline_context(pipeline_id: str) -> dict:
    """Return full pipeline graph (nodes, edges) for agent reasoning."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Pipeline)
            .where(Pipeline.id == UUID(pipeline_id))
            .options(selectinload(Pipeline.nodes), selectinload(Pipeline.edges))
        )
        pipeline = result.scalar_one_or_none()
        if pipeline is None:
            return {"error": "Pipeline not found"}
        await db.commit()
        return pipeline_to_read(pipeline).model_dump(mode="json")


@mcp.tool()
async def summarize_graph(pipeline_id: str) -> str:
    """Short text summary of the pipeline graph."""
    ctx = await get_pipeline_context(pipeline_id)
    if "error" in ctx:
        return ctx["error"]
    nodes = ctx.get("nodes", [])
    edges = ctx.get("edges", [])
    lines = [f"Pipeline: {ctx.get('name')} ({len(nodes)} nodes, {len(edges)} edges)"]
    for n in nodes:
        lines.append(f"  - [{n['type']}/{n['subtype']}] {n['label']} ({n['status']})")
    return "\n".join(lines)


@mcp.tool()
async def create_agent_task_tool(
    pipeline_id: str,
    agent_role: str,
    instruction: str,
    node_id: str | None = None,
) -> dict:
    """Delegate work to a specialized agent (stored as PENDING in MVP)."""
    async with async_session_factory() as db:
        try:
            role = AgentRole(agent_role)
        except ValueError:
            return {"error": f"Invalid agent_role: {agent_role}"}
        task = await create_agent_task(
            db,
            UUID(pipeline_id),
            agent_role=role,
            instruction=instruction,
            node_id=UUID(node_id) if node_id else None,
        )
        await db.commit()
        return {
            "id": str(task.id),
            "agent_role": task.agent_role.value,
            "status": task.status.value,
            "instruction": task.instruction,
        }


@mcp.tool()
async def stub_specialized_agent(agent_role: str) -> str:
    """Returns MVP stub message for non-Master agents."""
    return f"Agent {agent_role} is not available in MVP. Task can be queued as PENDING only."

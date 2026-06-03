import json
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_task import AgentTask
from app.models.enums import AgentRole
from app.services.chat_service import create_agent_task

SYSTEM_PROMPT = """You are the Master Agent for DataPipe, a visual ETL system for banking pipelines.
You orchestrate specialized agents (Profiler, Engineer, Debugger, Guardian, QA, Auditor).
Respond in Markdown. Be concise and actionable.

When the user needs data profiling, transformation code, or auditing, you may delegate by including
a JSON block at the end of your response (only when delegation is needed):

```delegation
[{"agent_role": "PROFILER", "instruction": "...", "node_id": null}]
```

Valid agent_role values: PROFILER, ENGINEER, DEBUGGER, GUARDIAN, QA, AUDITOR.
Specialized agents are NOT executed in MVP — tasks stay PENDING for human review.

Ask clarifying questions if the user has not uploaded data files or provided DB credentials.
"""


class MasterAgentRunner:
    def __init__(self, db: AsyncSession, pipeline_id: UUID) -> None:
        self.db = db
        self.pipeline_id = pipeline_id
        self.settings = get_settings()

    async def run(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> tuple[dict[str, Any], list[AgentTask]]:
        reply_text = await self._call_llm(user_content, pipeline_context, history)
        delegations, clean_content = self._parse_delegations(reply_text)

        new_tasks: list[AgentTask] = []
        for d in delegations:
            role_str = d.get("agent_role", "PROFILER")
            try:
                role = AgentRole(role_str)
            except ValueError:
                continue
            if role == AgentRole.MASTER:
                continue
            node_id = d.get("node_id")
            task = await create_agent_task(
                self.db,
                self.pipeline_id,
                agent_role=role,
                instruction=d.get("instruction", ""),
                node_id=UUID(node_id) if node_id else None,
            )
            new_tasks.append(task)

        metadata: dict[str, Any] = {}
        if delegations:
            metadata["delegations"] = delegations
        if "?" in clean_content or "upload" in clean_content.lower():
            metadata["requires_user_input"] = True

        return {"content": clean_content, "metadata": metadata}, new_tasks

    async def _call_llm(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        if self.settings.openai_api_key:
            return await self._openai_chat(user_content, pipeline_context, history)
        return self._fallback_response(user_content, pipeline_context)

    async def _openai_chat(
        self,
        user_content: str,
        pipeline_context: dict[str, Any],
        history: list[dict[str, str]],
    ) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        context_summary = json.dumps(
            {
                "pipeline_id": pipeline_context.get("id"),
                "name": pipeline_context.get("name"),
                "nodes": [
                    {"id": str(n["id"]), "type": n["type"], "subtype": n["subtype"], "label": n["label"]}
                    for n in pipeline_context.get("nodes", [])
                ],
                "edges": pipeline_context.get("edges", []),
            },
            indent=2,
        )
        messages.append({"role": "system", "content": f"Current pipeline context:\n{context_summary}"})
        for h in history[-10:]:
            role = "user" if h["sender"] == "USER" else "assistant"
            messages.append({"role": role, "content": h["content"]})
        messages.append({"role": "user", "content": user_content})

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.llm_model,
                    "messages": messages,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _fallback_response(self, user_content: str, pipeline_context: dict[str, Any]) -> str:
        nodes = pipeline_context.get("nodes", [])
        edges = pipeline_context.get("edges", [])
        summary = f"Pipeline **{pipeline_context.get('name')}** has {len(nodes)} node(s) and {len(edges)} edge(s)."
        reply = (
            f"{summary}\n\n"
            f"You asked: _{user_content}_\n\n"
            "I'm running in **offline mode** (no `OPENAI_API_KEY`). "
            "Set the API key to enable full Master Agent reasoning.\n\n"
        )
        if "profil" in user_content.lower() or "anomal" in user_content.lower():
            reply += (
                "I would delegate profiling to the Profiler agent.\n\n"
                '```delegation\n[{"agent_role": "PROFILER", "instruction": '
                f'"Profile pipeline data per user request: {user_content[:200]}", "node_id": null}]\n```'
            )
        elif nodes:
            reply += "Describe the transformation you need, or upload a CSV/JSON source file to continue."
        else:
            reply += "Add SOURCE nodes (CSV/JSON) to the canvas to begin building your ETL flow."
        return reply

    def _parse_delegations(self, text: str) -> tuple[list[dict[str, Any]], str]:
        pattern = r"```delegation\s*([\s\S]*?)```"
        match = re.search(pattern, text)
        if not match:
            return [], text.strip()
        try:
            delegations = json.loads(match.group(1).strip())
            if isinstance(delegations, dict):
                delegations = [delegations]
        except json.JSONDecodeError:
            delegations = []
        clean = re.sub(pattern, "", text).strip()
        return delegations, clean

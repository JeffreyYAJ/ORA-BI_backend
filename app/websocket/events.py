from enum import Enum
from typing import Any

from pydantic import BaseModel


class WsEventType(str, Enum):
    PIPELINE_UPDATED = "pipeline.updated"
    NODE_CREATED = "node.created"
    NODE_UPDATED = "node.updated"
    NODE_DELETED = "node.deleted"
    EDGE_CREATED = "edge.created"
    EDGE_DELETED = "edge.deleted"
    CHAT_MESSAGE = "chat.message"
    AGENT_TASK_UPDATED = "agent_task.updated"
    GUARDIAN_APPROVAL_REQUIRED = "guardian.approval_required"
    GUARDIAN_APPROVAL_RESOLVED = "guardian.approval_resolved"
    PIPELINE_RUN_UPDATED = "pipeline.run_updated"
    PIPELINE_RUN_EVENT = "pipeline.run_event"
    USER_INPUT_REQUIRED = "user_input.required"
    USER_INPUT_ANSWERED = "user_input.answered"


class WsEvent(BaseModel):
    type: WsEventType
    pipeline_id: str
    payload: dict[str, Any]

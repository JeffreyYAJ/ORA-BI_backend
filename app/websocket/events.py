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


class WsEvent(BaseModel):
    type: WsEventType
    pipeline_id: str
    payload: dict[str, Any]

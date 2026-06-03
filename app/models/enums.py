import enum


class NodeType(str, enum.Enum):
    SOURCE = "SOURCE"
    TRANSFORM = "TRANSFORM"
    SINK = "SINK"


class NodeSubtype(str, enum.Enum):
    CSV = "csv"
    JSON = "json"
    PYTHON_SCRIPT = "python_script"
    SQL_QUERY = "sql_query"
    POSTGRES_SINK = "postgres_sink"
    SQLITE = "sqlite"
    GENERIC = "generic"


class NodeStatus(str, enum.Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    VALID = "VALID"
    ERROR = "ERROR"


class PipelineStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ChatSender(str, enum.Enum):
    USER = "USER"
    MASTER_AGENT = "MASTER_AGENT"


class AgentRole(str, enum.Enum):
    MASTER = "MASTER"
    PROFILER = "PROFILER"
    ENGINEER = "ENGINEER"
    DEBUGGER = "DEBUGGER"
    GUARDIAN = "GUARDIAN"
    QA = "QA"
    AUDITOR = "AUDITOR"


class AgentTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

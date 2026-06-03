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
    GUARDIAN_AGENT = "GUARDIAN_AGENT"


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


class PipelineRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_USER_INPUT = "AWAITING_USER_INPUT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GuardianOperationType(str, enum.Enum):
    DELETE_COLUMN = "DELETE_COLUMN"
    EXPORT_DATA = "EXPORT_DATA"
    SINK_WRITE = "SINK_WRITE"
    BULK_TRANSFORM = "BULK_TRANSFORM"
    PII_EXPOSURE = "PII_EXPOSURE"
    PIPELINE_RUN = "PIPELINE_RUN"
    CUSTOM = "CUSTOM"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserQuestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"


class WorkflowPhase(str, enum.Enum):
    INITIAL_STUDY = "INITIAL_STUDY"
    AGENT_TASK = "AGENT_TASK"
    NODE_EXECUTION = "NODE_EXECUTION"
    CHAT = "CHAT"


class PipelineRunEventType(str, enum.Enum):
    RUN_STARTED = "RUN_STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    PII_DETECTED = "PII_DETECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    GUARDIAN_QUESTION = "GUARDIAN_QUESTION"
    USER_QUESTION = "USER_QUESTION"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"

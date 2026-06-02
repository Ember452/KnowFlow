"""全局常量与枚举 - 执行域 / 任务状态 / SSE 事件类型 / 错误码前缀."""

from enum import StrEnum


class ExecutionDomain(StrEnum):
    """工具执行域. 决定工具对 LLM 的可见性."""

    DIRECT = "direct"  # 主 Agent 始终可见
    SKILL_ONLY = "skill_only"  # Skill 激活后注入
    SUBAGENT_ONLY = "subagent_only"  # 仅子 Agent 可见
    INTERNAL = "internal"  # 系统内部, 不暴露给模型


class TaskStatus(StrEnum):
    """任务/Agent 运行状态."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class DelegationStatus(StrEnum):
    """任务委派状态机."""

    CREATED = "created"
    DELEGATED = "delegated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SSEEventType(StrEnum):
    """SSE 流式事件类型."""

    TOKEN = "token"  # LLM token 流
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    RETRIEVAL = "retrieval"
    PROGRESS = "progress"
    DONE = "done"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class DocumentStatus(StrEnum):
    """文档索引状态."""

    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class SpanType(StrEnum):
    """Trace Span 类型."""

    AGENT_DECISION = "agent_decision"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    MEMORY_RECALL = "memory_recall"


# ── 错误码前缀(模块标识) ──
ERR_PREFIX_RETRIEVAL = "RETR"
ERR_PREFIX_TOOLS = "TOOL"
ERR_PREFIX_CONTEXT = "CTX"
ERR_PREFIX_AGENTS = "AGNT"
ERR_PREFIX_SANDBOX = "SBX"
ERR_PREFIX_MEMORY = "MEM"
ERR_PREFIX_API = "API"
ERR_PREFIX_DB = "DB"

# ── 限流默认值 ──
DEFAULT_RATE_LIMIT_PER_MINUTE = 60

# ── 检索默认参数 ──
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_TOP_K = 10
RRF_K = 60  # Reciprocal Rank Fusion 经典参数

# ── Agent 编排默认参数 ──
MAX_TOOL_ROUNDS = 5  # 工具调用最大轮数
DEFAULT_SUBAGENT_TIMEOUT = 60  # 子 Agent 超时(秒)
MEMORY_SEDIMENT_INTERVAL = 5  # 每 N 轮触发一次记忆沉淀

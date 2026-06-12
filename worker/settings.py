"""Worker 专用配置 - 从全局 Settings 派生索引 worker 所需参数."""

from dataclasses import dataclass

from knowflow.core.config import get_settings


@dataclass(frozen=True)
class WorkerSettings:
    """索引 Worker 运行参数."""

    stream: str
    dlq_stream: str
    group: str
    consumer: str
    max_retries: int
    block_ms: int
    batch_size: int = 1

    @classmethod
    def from_settings(cls) -> "WorkerSettings":
        s = get_settings()
        return cls(
            stream=s.task_stream_index,
            dlq_stream=s.task_stream_dlq,
            group=s.task_consumer_group,
            consumer=s.task_consumer_name,
            max_retries=s.task_max_retries,
            block_ms=s.task_block_ms,
        )

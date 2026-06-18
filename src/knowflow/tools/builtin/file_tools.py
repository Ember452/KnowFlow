"""沙盒文件工具 - read/write/list, 经 WorkspaceManager 操作会话级沙盒.

skill_only 域(由 data_analysis/code_review 等 Skill 激活). 工具接收 session_id 与
虚拟路径, 内部映射到沙盒后端. 写操作受配额约束, 跨会话访问被拦截.
"""

import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import BaseTool, ToolResult


class _FileToolBase(BaseTool):
    """文件工具公共基类: 持有 WorkspaceManager, 提供 session 级 FileOps."""

    domain = ExecutionDomain.SKILL_ONLY

    def __init__(self, workspace_manager: Any) -> None:
        self._ws = workspace_manager

    def _for_session(self, session_id: int | str) -> Any:
        return self._ws.for_session(session_id)


class FileReadTool(_FileToolBase):
    """读取沙盒文件. skill_only 域."""

    name = "file_read_tool"
    description = "读取当前会话沙盒工作区中的文件内容. 输入 session_id 与虚拟路径."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 id"},
                "path": {"type": "string", "description": "虚拟路径, 如 /workspace/result.json"},
            },
            "required": ["session_id", "path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        session_id = str(kwargs.get("session_id", ""))
        path = str(kwargs.get("path", ""))
        try:
            content = await self._for_session(session_id).read(path)
            latency_ms = (time.perf_counter() - start) * 1000
            # 文本优先返回 str, 便于 LLM 消费; 非文本返回字节长度
            try:
                output: Any = content.decode("utf-8")
            except UnicodeDecodeError:
                output = {"bytes": len(content), "note": "非文本文件, 无法解码为字符串"}
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )


class FileWriteTool(_FileToolBase):
    """写入沙盒文件(受配额约束). skill_only 域."""

    name = "file_write_tool"
    description = "向当前会话沙盒工作区写入文件. 输入 session_id、虚拟路径与内容."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 id"},
                "path": {"type": "string", "description": "虚拟路径, 如 /workspace/out.csv"},
                "content": {"type": "string", "description": "文件文本内容"},
            },
            "required": ["session_id", "path", "content"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        session_id = str(kwargs.get("session_id", ""))
        path = str(kwargs.get("path", ""))
        content = str(kwargs.get("content", ""))
        try:
            data = content.encode("utf-8")
            written = await self._for_session(session_id).write(path, data, "text/plain")
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output={"path": written, "bytes": len(data)},
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )


class FileListTool(_FileToolBase):
    """列出沙盒工作区文件. skill_only 域."""

    name = "file_list_tool"
    description = "列出当前会话沙盒工作区的文件. 输入 session_id, 可选目录路径."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 id"},
                "dir": {
                    "type": "string",
                    "description": "虚拟目录, 默认 /workspace/",
                    "default": "/workspace/",
                },
            },
            "required": ["session_id"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        session_id = str(kwargs.get("session_id", ""))
        dir_ = str(kwargs.get("dir", "/workspace/"))
        try:
            files = await self._for_session(session_id).list(dir_)
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=[{"path": f.virtual_path, "size": f.size} for f in files],
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )

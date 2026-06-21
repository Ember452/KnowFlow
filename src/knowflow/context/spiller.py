"""工具结果卸载 - 超阈值文本写入沙盒文件, 以引用替换注入上下文.

长工具结果(如搜索返回超长文本)超过 spill_threshold_tokens 时, 写入
会话沙盒 /workspace/spilled/ 目录, 上下文仅注入
{"spilled": true, "path": "/workspace/..."} 引用, LLM 需要时可经
file_read_tool 读回. 沙盒后端由 M5(P9) 提供, 直接复用 WorkspaceManager.
"""

import time
from dataclasses import dataclass
from typing import Any

from knowflow.context.token_counter import TokenCounter
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_SPILLED_DIR = "/workspace/spilled"


@dataclass(frozen=True)
class SpillResult:
    """卸载结果. spilled=True 时 text 为原始内容, path 为沙盒路径."""

    spilled: bool
    text: str
    path: str | None = None

    def reference(self) -> str:
        """生成注入上下文的引用文本(LLM 可读)."""
        return f'{{"spilled": true, "path": "{self.path}"}}'


class Spiller:
    """工具结果卸载器. 超阈值写入沙盒并以引用替换."""

    def __init__(
        self,
        workspace_manager: Any,
        settings: Settings | None = None,
        counter: TokenCounter | None = None,
    ) -> None:
        self._ws = workspace_manager
        self._settings = settings or get_settings()
        self._counter = counter or TokenCounter(settings=self._settings)

    async def spill_if_needed(self, text: str, session_id: int | str) -> SpillResult:
        """文本超阈值时卸载到会话沙盒; 未超阈值原样返回.

        Args:
            text: 工具结果/长文本.
            session_id: 会话 id(沙盒隔离).

        Returns:
            SpillResult: spilled=True 时 text 为原文, path 为沙盒虚拟路径.
        """
        if not text or not self._counter.exceeds(text, self._settings.spill_threshold_tokens):
            return SpillResult(spilled=False, text=text)
        path = f"{_SPILLED_DIR}/{int(time.time() * 1000)}.txt"
        await self._ws.for_session(session_id).write(path, text.encode("utf-8"), "text/plain")
        logger.info(
            "context.spilled",
            session_id=str(session_id),
            path=path,
            chars=len(text),
        )
        return SpillResult(spilled=True, text=text, path=path)

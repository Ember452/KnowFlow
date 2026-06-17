"""访问控制 - 校验虚拟路径不越界当前会话 workspace.

拦截: 路径穿越(../)、非绝对路径、非 workspace 前缀. 仅允许 /workspace/ 内操作,
保证工具无法逃逸沙盒或读写其他会话文件. session_id 隔离由 VirtualPathMapper
在映射层保证, 本模块只做路径合法性校验.
"""

import re

from knowflow.core.exceptions import PermissionDeniedError

WORKSPACE_PREFIX = "/workspace"
# 匹配独立的 .. 段: /../ /foo/.. /.. 等均命中
_TRAVERSAL = re.compile(r"(?:^|/)\.\.(?:/|$)")


def _normalize(path: str) -> str:
    """合并连续斜杠, 保证 /workspace 与 /workspace/ 均合法."""
    norm = re.sub(r"/+", "/", path)
    # /workspace 视为根目录, 统一带尾斜杠
    if norm == WORKSPACE_PREFIX:
        return f"{WORKSPACE_PREFIX}/"
    return norm


class AccessControl:
    """沙盒路径访问控制. 每个 session 一个实例."""

    def __init__(self, session_id: int | str) -> None:
        self._session_id = str(session_id)

    @property
    def session_id(self) -> str:
        return self._session_id

    def validate(self, virtual_path: str) -> str:
        """校验虚拟路径合法性, 返回规范化后的路径; 非法则抛 PermissionDeniedError."""
        if not virtual_path or not virtual_path.startswith("/"):
            raise PermissionDeniedError(f"虚拟路径必须为绝对路径: {virtual_path!r}")
        if not virtual_path.startswith(WORKSPACE_PREFIX):
            raise PermissionDeniedError(f"路径不在 workspace 范围内: {virtual_path!r}")
        if _TRAVERSAL.search(virtual_path):
            raise PermissionDeniedError(f"检测到路径穿越: {virtual_path!r}")
        # /workspacex 之类前缀伪造: 确保紧跟 / 或结尾
        tail = virtual_path[len(WORKSPACE_PREFIX) :]
        if tail and not tail.startswith("/"):
            raise PermissionDeniedError(f"路径不在 workspace 范围内: {virtual_path!r}")
        return _normalize(virtual_path)

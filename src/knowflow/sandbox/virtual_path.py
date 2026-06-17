"""虚拟路径映射 - /workspace/xxx ↔ MinIO key sessions/{sid}/workspace/xxx.

沙盒对工具暴露统一虚拟路径(如 /workspace/result.json), 内部映射到 MinIO 对象 key
(如 sessions/42/workspace/result.json). 工具不感知 session 前缀与存储后端,
跨会话访问在映射层即被拒绝.
"""

from knowflow.core.exceptions import ValidationError

WORKSPACE_PREFIX = "/workspace"  # 虚拟路径根
_WORKSPACE_SEGMENT = "workspace"  # MinIO key 中的 workspace 段


class VirtualPathMapper:
    """虚拟路径 ↔ MinIO key 双向映射(按 session_id 隔离)."""

    def __init__(self, session_id: int | str) -> None:
        self._session_id = str(session_id)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_prefix(self) -> str:
        """该会话 workspace 在 MinIO 的 key 前缀(不含尾斜杠)."""
        return f"sessions/{self._session_id}/{_WORKSPACE_SEGMENT}"

    def to_real(self, virtual_path: str) -> str:
        """虚拟路径 → MinIO key.

        仅做前缀替换, 路径越界(../)由 AccessControl 提前拦截. 入参必须已通过校验.
        /workspace/         → sessions/{sid}/workspace/
        /workspace/a.json   → sessions/{sid}/workspace/a.json
        """
        rel = self._strip_prefix(virtual_path)
        return f"{self.session_prefix}/{rel}" if rel else f"{self.session_prefix}/"

    def to_virtual(self, real_key: str) -> str:
        """MinIO key → 虚拟路径. 非当前会话 workspace 的 key 抛错(跨会话拦截)."""
        prefix = self.session_prefix
        if real_key == prefix:
            return f"{WORKSPACE_PREFIX}/"
        if not real_key.startswith(prefix + "/"):
            raise ValidationError(f"对象不属于当前会话 workspace: {real_key}")
        rel = real_key[len(prefix) + 1 :]
        return f"{WORKSPACE_PREFIX}/{rel}"

    def _strip_prefix(self, virtual_path: str) -> str:
        if not virtual_path.startswith(WORKSPACE_PREFIX):
            raise ValidationError(f"虚拟路径必须以 {WORKSPACE_PREFIX} 开头: {virtual_path}")
        rel = virtual_path[len(WORKSPACE_PREFIX) :]
        # /workspace 后必须为空或紧跟 /
        if rel and not rel.startswith("/"):
            raise ValidationError(f"非法虚拟路径: {virtual_path}")
        return rel.lstrip("/")

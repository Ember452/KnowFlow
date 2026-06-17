"""沙盒文件系统单测 - 虚拟路径/访问控制/文件操作/配额/工作区.

用 FakeMinio(内存对象存储)验证: 路径穿越拦截、跨会话隔离、CRUD 正确性、配额超限.
不依赖真实 MinIO 容器.
"""

import pytest

from knowflow.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from knowflow.sandbox.access_control import AccessControl
from knowflow.sandbox.virtual_path import VirtualPathMapper
from knowflow.sandbox.workspace import WorkspaceManager
from tests.fakes import FakeMinio

# ── VirtualPathMapper ──


class TestVirtualPathMapper:
    def test_to_real_maps_workspace_prefix(self) -> None:
        m = VirtualPathMapper("42")
        assert m.to_real("/workspace/a.json") == "sessions/42/workspace/a.json"
        assert m.to_real("/workspace/") == "sessions/42/workspace/"
        assert m.session_prefix == "sessions/42/workspace"

    def test_to_virtual_reverse(self) -> None:
        m = VirtualPathMapper(7)
        assert m.to_virtual("sessions/7/workspace/x.csv") == "/workspace/x.csv"
        assert m.to_virtual("sessions/7/workspace") == "/workspace/"

    def test_to_virtual_rejects_other_session(self) -> None:
        m = VirtualPathMapper(1)
        with pytest.raises(ValidationError):
            m.to_virtual("sessions/2/workspace/secret.json")

    def test_to_real_rejects_non_workspace(self) -> None:
        m = VirtualPathMapper(1)
        with pytest.raises(ValidationError):
            m.to_real("/etc/passwd")


# ── AccessControl ──


class TestAccessControl:
    @pytest.mark.parametrize(
        "path",
        ["/workspace/../etc/passwd", "/workspace/foo/../../bar", "/workspace/.."],
    )
    def test_blocks_traversal(self, path: str) -> None:
        with pytest.raises(PermissionDeniedError):
            AccessControl(1).validate(path)

    @pytest.mark.parametrize(
        "path",
        ["workspace/a.json", "etc/passwd", "relative/path"],
    )
    def test_rejects_non_absolute(self, path: str) -> None:
        with pytest.raises(PermissionDeniedError):
            AccessControl(1).validate(path)

    def test_rejects_non_workspace_prefix(self) -> None:
        with pytest.raises(PermissionDeniedError):
            AccessControl(1).validate("/etc/passwd")
        # /workspacex 伪造前缀
        with pytest.raises(PermissionDeniedError):
            AccessControl(1).validate("/workspacex/foo")

    def test_normalizes_and_accepts_root(self) -> None:
        ac = AccessControl(1)
        assert ac.validate("/workspace/") == "/workspace/"
        assert ac.validate("/workspace") == "/workspace/"
        assert ac.validate("/workspace//a//b.json") == "/workspace/a/b.json"


# ── FileOps + WorkspaceManager ──


@pytest.fixture
def manager() -> WorkspaceManager:
    return WorkspaceManager(FakeMinio())


class TestFileOps:
    async def test_write_read_roundtrip(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        await ws.write("/workspace/result.json", b'{"k": 1}', "application/json")
        assert await ws.read("/workspace/result.json") == b'{"k": 1}'
        assert await ws.exists("/workspace/result.json")

    async def test_write_nested_path(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        await ws.write("/workspace/reports/q1.csv", b"a,b\n1,2")
        assert await ws.read("/workspace/reports/q1.csv") == b"a,b\n1,2"

    async def test_read_not_found(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        with pytest.raises(NotFoundError):
            await ws.read("/workspace/missing.json")

    async def test_list_recursive(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        await ws.write("/workspace/a.json", b"{}")
        await ws.write("/workspace/sub/b.json", b"{}")
        names = {f.virtual_path for f in await ws.list("/workspace/")}
        assert "/workspace/a.json" in names
        assert "/workspace/sub/b.json" in names

    async def test_delete(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        await ws.write("/workspace/x.txt", b"hi")
        assert await ws.delete("/workspace/x.txt") is True
        assert await ws.delete("/workspace/x.txt") is False  # 幂等
        assert await ws.exists("/workspace/x.txt") is False

    async def test_cross_session_isolation(self, manager: WorkspaceManager) -> None:
        ws_a = manager.for_session(1)
        ws_b = manager.for_session(2)
        await ws_a.write("/workspace/secret.json", b"private")
        # 会话 B 读不到会话 A 的文件
        assert await ws_b.exists("/workspace/secret.json") is False
        with pytest.raises(NotFoundError):
            await ws_b.read("/workspace/secret.json")

    async def test_write_blocks_traversal(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        with pytest.raises(PermissionDeniedError):
            await ws.write("/workspace/../escape.json", b"x")


class TestQuota:
    async def test_quota_rejects_oversize(self) -> None:
        from knowflow.core.config import Settings

        # 配额设为 10 字节, 写 20 字节应被拒
        settings = Settings(workspace_quota_bytes=10, env="test")
        manager = WorkspaceManager(FakeMinio(), settings)
        ws = manager.for_session(1)
        with pytest.raises(ValidationError):
            await ws.write("/workspace/big.bin", b"x" * 20)

    async def test_quota_accumulates(self) -> None:
        from knowflow.core.config import Settings

        settings = Settings(workspace_quota_bytes=15, env="test")
        manager = WorkspaceManager(FakeMinio(), settings)
        ws = manager.for_session(1)
        await ws.write("/workspace/a.bin", b"x" * 10)  # 用 10
        with pytest.raises(ValidationError):  # 再写 10 超限(10+10>15)
            await ws.write("/workspace/b.bin", b"x" * 10)
        assert await ws.usage() == 10


class TestWorkspaceManager:
    async def test_cleanup_removes_all(self, manager: WorkspaceManager) -> None:
        ws = manager.for_session(1)
        await ws.write("/workspace/a.json", b"{}")
        await ws.write("/workspace/b.json", b"{}")
        removed = await manager.cleanup(1)
        assert removed == 2
        assert await ws.list("/workspace/") == []

    async def test_cleanup_only_target_session(self, manager: WorkspaceManager) -> None:
        ws_a = manager.for_session(1)
        ws_b = manager.for_session(2)
        await ws_a.write("/workspace/a.json", b"{}")
        await ws_b.write("/workspace/b.json", b"{}")
        await manager.cleanup(1)
        assert await ws_a.list("/workspace/") == []
        assert len(await ws_b.list("/workspace/")) == 1

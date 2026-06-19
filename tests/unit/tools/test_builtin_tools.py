"""内置工具单测 - 计算器/知识检索/沙盒文件/网络搜索.

calculator: 安全 AST 求值, 拦截非数学节点.
retrieval_tool: 调 fake retriever 返回片段, content 截断.
file_tools: 经 WorkspaceManager + FakeMinio 验证读写列表, skill_only 域.
search_tool: subagent_only 域, 依赖未安装时返回失败 ToolResult.
"""

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.sandbox.workspace import WorkspaceManager
from knowflow.tools.builtin.calculator import CalculatorTool
from knowflow.tools.builtin.file_tools import FileListTool, FileReadTool, FileWriteTool
from knowflow.tools.builtin.retrieval_tool import RetrievalTool
from knowflow.tools.builtin.search_tool import SearchTool
from tests.fakes import FakeChunkWithScore, FakeMinio, FakeRetriever

# ── CalculatorTool ──


class TestCalculator:
    async def test_basic_arithmetic(self) -> None:
        """基础四则运算正确."""
        r = await CalculatorTool().execute(expression="1 + 2 * 3")
        assert r.success is True
        assert r.output == 7

    async def test_power(self) -> None:
        """幂运算正确(2^10 = 1024)."""
        r = await CalculatorTool().execute(expression="2**10")
        assert r.success is True
        assert r.output == 1024

    async def test_parentheses(self) -> None:
        """括号优先级正确."""
        r = await CalculatorTool().execute(expression="(1 + 2) * 3")
        assert r.success is True
        assert r.output == 9

    async def test_unary_minus(self) -> None:
        """一元负号正确."""
        r = await CalculatorTool().execute(expression="-5 + 3")
        assert r.success is True
        assert r.output == -2

    async def test_floor_div_and_mod(self) -> None:
        """整除与取模正确."""
        r = await CalculatorTool().execute(expression="17 // 5")
        assert r.output == 3
        r2 = await CalculatorTool().execute(expression="17 % 5")
        assert r2.output == 2

    async def test_rejects_name_injection(self) -> None:
        """名称节点(变量/函数调用)被拦截, 防代码注入."""
        r = await CalculatorTool().execute(expression="__import__('os')")
        assert r.success is False
        assert "不允许" in (r.error or "")

    async def test_rejects_attribute_access(self) -> None:
        """属性访问被拦截."""
        r = await CalculatorTool().execute(expression="(1).bit_length()")
        assert r.success is False

    async def test_empty_expression(self) -> None:
        """空表达式返回失败."""
        r = await CalculatorTool().execute(expression="")
        assert r.success is False

    async def test_too_long_expression(self) -> None:
        """超长表达式(>200 字符)被拒."""
        r = await CalculatorTool().execute(expression="1+" * 150)
        assert r.success is False
        assert "过长" in (r.error or "")

    def test_domain_is_direct(self) -> None:
        """calculator 为 direct 域, 主 Agent 始终可见."""
        assert CalculatorTool.domain == ExecutionDomain.DIRECT

    def test_input_schema(self) -> None:
        """schema 含 expression 字段."""
        schema = CalculatorTool().input_schema()
        assert "expression" in schema["properties"]
        assert schema["required"] == ["expression"]


# ── RetrievalTool ──


class TestRetrievalTool:
    async def test_retrieve_returns_chunks(self) -> None:
        """调 retriever 返回片段, content 截断至 500 字符."""
        chunks = [FakeChunkWithScore(chunk_id=1, content="知识内容", score=0.9, source="doc.md")]
        tool = RetrievalTool(FakeRetriever(chunks=chunks))
        r = await tool.execute(query="报销流程")
        assert r.success is True
        assert r.output["count"] == 1
        assert r.output["chunks"][0]["content"] == "知识内容"
        assert r.output["chunks"][0]["chunk_id"] == 1

    async def test_retrieve_truncates_long_content(self) -> None:
        """超长 content 截断至 500 字符."""
        long_text = "x" * 600
        chunks = [FakeChunkWithScore(chunk_id=1, content=long_text, score=1.0, source="")]
        tool = RetrievalTool(FakeRetriever(chunks=chunks))
        r = await tool.execute(query="q")
        assert len(r.output["chunks"][0]["content"]) == 500

    async def test_retrieve_failure(self) -> None:
        """retriever 异常时返回失败 ToolResult."""

        class _BoomRetriever:
            async def retrieve(self, query: str, **kw: object) -> None:
                raise RuntimeError("连接失败")

        tool = RetrievalTool(_BoomRetriever())
        r = await tool.execute(query="q")
        assert r.success is False
        assert "连接失败" in (r.error or "")

    async def test_retrieve_passes_top_k(self) -> None:
        """top_k 透传给 retriever."""
        retriever = FakeRetriever(chunks=[])
        tool = RetrievalTool(retriever)
        await tool.execute(query="q", top_k=10)
        assert retriever.calls[0]["top_k"] == 10

    def test_domain_is_direct(self) -> None:
        """retrieval_tool 为 direct 域."""
        assert RetrievalTool.domain == ExecutionDomain.DIRECT


# ── FileTools ──


@pytest.fixture
def ws_manager() -> WorkspaceManager:
    """基于 FakeMinio 的沙盒管理器(每用例独立)."""
    return WorkspaceManager(FakeMinio())


class TestFileTools:
    async def test_write_then_read(self, ws_manager: WorkspaceManager) -> None:
        """写入后可读回."""
        write_tool = FileWriteTool(ws_manager)
        read_tool = FileReadTool(ws_manager)
        w = await write_tool.execute(session_id="1", path="/workspace/a.txt", content="hello")
        assert w.success is True
        assert w.output["bytes"] == 5
        r = await read_tool.execute(session_id="1", path="/workspace/a.txt")
        assert r.success is True
        assert r.output == "hello"

    async def test_write_returns_path(self, ws_manager: WorkspaceManager) -> None:
        """write 返回规范化虚拟路径."""
        write_tool = FileWriteTool(ws_manager)
        w = await write_tool.execute(session_id="1", path="/workspace/sub/b.json", content="{}")
        assert w.output["path"] == "/workspace/sub/b.json"

    async def test_read_not_found(self, ws_manager: WorkspaceManager) -> None:
        """读不存在文件返回失败."""
        read_tool = FileReadTool(ws_manager)
        r = await read_tool.execute(session_id="1", path="/workspace/missing.txt")
        assert r.success is False

    async def test_list_files(self, ws_manager: WorkspaceManager) -> None:
        """列出已写入的文件."""
        write_tool = FileWriteTool(ws_manager)
        list_tool = FileListTool(ws_manager)
        await write_tool.execute(session_id="1", path="/workspace/a.txt", content="x")
        await write_tool.execute(session_id="1", path="/workspace/b.txt", content="yy")
        r = await list_tool.execute(session_id="1")
        assert r.success is True
        paths = {f["path"] for f in r.output}
        assert "/workspace/a.txt" in paths
        assert "/workspace/b.txt" in paths

    async def test_cross_session_isolation(self, ws_manager: WorkspaceManager) -> None:
        """会话 A 写的文件, 会话 B 读不到."""
        write_tool = FileWriteTool(ws_manager)
        read_tool = FileReadTool(ws_manager)
        await write_tool.execute(session_id="1", path="/workspace/secret.txt", content="private")
        r = await read_tool.execute(session_id="2", path="/workspace/secret.txt")
        assert r.success is False

    async def test_write_blocks_traversal(self, ws_manager: WorkspaceManager) -> None:
        """路径穿越被拦截."""
        write_tool = FileWriteTool(ws_manager)
        r = await write_tool.execute(session_id="1", path="/workspace/../etc/passwd", content="x")
        assert r.success is False

    async def test_read_binary_returns_bytes_note(self, ws_manager: WorkspaceManager) -> None:
        """非文本文件读取返回字节长度信息(解码失败返回长度)."""
        # 直接通过 workspace 写入二进制(绕过 text 编码)
        bin_data = b"\xff\xfe\x00\x01"  # 非 UTF-8
        await ws_manager.for_session("1").write("/workspace/bin.dat", bin_data)
        read_tool = FileReadTool(ws_manager)
        r = await read_tool.execute(session_id="1", path="/workspace/bin.dat")
        assert r.success is True
        assert isinstance(r.output, dict)
        assert r.output["bytes"] == 4

    def test_domain_is_skill_only(self) -> None:
        """文件工具为 skill_only 域."""
        ws = WorkspaceManager(FakeMinio())
        assert FileReadTool(ws).domain == ExecutionDomain.SKILL_ONLY
        assert FileWriteTool(ws).domain == ExecutionDomain.SKILL_ONLY
        assert FileListTool(ws).domain == ExecutionDomain.SKILL_ONLY


# ── SearchTool ──


class TestSearchTool:
    def test_domain_is_subagent_only(self) -> None:
        """search_tool 为 subagent_only 域, 仅子 Agent 可见."""
        assert SearchTool.domain == ExecutionDomain.SUBAGENT_ONLY

    async def test_execute_without_dependency_returns_failure(self) -> None:
        """未安装 duckduckgo_search 时返回失败 ToolResult(不抛异常)."""
        # monkeypatch sys.modules 使导入失败
        import sys

        original = sys.modules.pop("duckduckgo_search", None)
        # 注入一个找不到模块的查找器
        import importlib.abc
        import importlib.machinery

        class _Blocker(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path, target=None):  # type: ignore[no-untyped-def]
                if fullname == "duckduckgo_search":
                    raise ImportError("blocked for test")
                return None

        blocker = _Blocker()
        sys.meta_path.insert(0, blocker)
        try:
            r = await SearchTool().execute(query="test")
            assert r.success is False
            assert "未安装" in (r.error or "") or "blocked" in (r.error or "")
        finally:
            sys.meta_path.remove(blocker)
            if original is not None:
                sys.modules["duckduckgo_search"] = original

    def test_input_schema(self) -> None:
        """schema 含 query 与 max_results."""
        schema = SearchTool().input_schema()
        assert "query" in schema["properties"]
        assert "max_results" in schema["properties"]
        assert schema["required"] == ["query"]

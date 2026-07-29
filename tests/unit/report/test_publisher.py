"""报告发布器单测 - 幂等/重试/凭证降级/单章失败标记/MCP 适配."""

from typing import Any

import pytest

from knowflow.agents.report.models import Chapter, ReportResult, ReportSpec, ReviewResult
from knowflow.agents.report.publisher import McpPublishAdapter, ReportPublisher
from knowflow.tools.base import ToolResult


class _FakeAdapter:
    """可脚本化发布适配器: 记录调用, 可注入失败序列."""

    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str]] = []
        self.append_calls: list[tuple[str, str]] = []
        self.update_calls: list[tuple[str, str, str]] = []
        self.create_failures: list[Exception] = []  # 依次抛错, 耗尽后成功
        self.append_failures: dict[str, Exception] = {}  # 章节标题 → 抛错
        self.doc_token = "doc_abc123"

    async def create_doc(self, title: str, content: str = "") -> dict[str, Any]:
        self.create_calls.append((title, content))
        if self.create_failures:
            raise self.create_failures.pop(0)
        return {"doc_token": self.doc_token, "url": f"https://feishu.cn/docx/{self.doc_token}"}

    async def append_to_doc(self, doc_token: str, content: str) -> dict[str, Any]:
        self.append_calls.append((doc_token, content))
        for title, exc in self.append_failures.items():
            if f"## {title}" in content:
                raise exc
        return {"appended": True}

    async def update_doc(self, doc_token: str, content: str, title: str = "") -> dict[str, Any]:
        self.update_calls.append((doc_token, content, title))
        return {"updated": True}


def _result(run_id: str = "r1") -> ReportResult:
    return ReportResult(
        run_id=run_id,
        spec=ReportSpec(title="报告", chapters=["一", "二"]),
        chapters=[
            Chapter(title="一", body="章节一正文 [1]。"),
            Chapter(title="二", body="章节二正文 [1]。"),
        ],
        review=ReviewResult(passed=True),
    )


@pytest.mark.asyncio
async def test_publish_success() -> None:
    """正常发布: 创建文档 + 分章节追加, 返回文档链接."""
    adapter = _FakeAdapter()
    resp = await ReportPublisher(adapter=adapter).publish(_result())
    assert resp["published"] is True
    assert resp["doc_url"] == "https://feishu.cn/docx/doc_abc123"
    assert adapter.create_calls[0][0] == "报告"
    assert len(adapter.append_calls) == 2
    assert "## 一" in adapter.append_calls[0][1]


@pytest.mark.asyncio
async def test_publish_retries_then_succeeds() -> None:
    """create 首次失败 → 指数退避重试(测试注入 0 延迟) → 成功."""
    adapter = _FakeAdapter()
    adapter.create_failures = [RuntimeError("网络抖动")]
    publisher = ReportPublisher(adapter=adapter, retry_delays=(0, 0, 0))
    resp = await publisher.publish(_result())
    assert resp["published"] is True
    assert len(adapter.create_calls) == 2  # 首次失败 + 重试成功


@pytest.mark.asyncio
async def test_publish_retries_exhausted_degrades() -> None:
    """重试耗尽 → 返回可读失败(不抛出), 报告仍可从沙盒获取."""
    adapter = _FakeAdapter()
    adapter.create_failures = [
        RuntimeError("失败1"),
        RuntimeError("失败2"),
        RuntimeError("失败3"),
        RuntimeError("失败4"),
    ]
    publisher = ReportPublisher(adapter=adapter, retry_delays=(0, 0, 0))
    resp = await publisher.publish(_result())
    assert resp["published"] is False
    assert "重试 3 次后" in resp["message"]
    assert len(adapter.create_calls) == 4  # 首次 + 3 次重试


@pytest.mark.asyncio
async def test_publish_credential_error_no_retry_readable() -> None:
    """凭证错误不重试, 返回"请重新授权飞书"可读提示."""
    adapter = _FakeAdapter()
    adapter.create_failures = [RuntimeError("invalid token: 99991663")]
    publisher = ReportPublisher(adapter=adapter, retry_delays=(0, 0, 0))
    resp = await publisher.publish(_result())
    assert resp["published"] is False
    assert "请重新授权飞书" in resp["message"]
    assert len(adapter.create_calls) == 1  # 凭证错误直接失败


@pytest.mark.asyncio
async def test_publish_idempotent_second_uses_update() -> None:
    """幂等: 重复 publish 走 update_doc, 不重复创建文档."""
    adapter = _FakeAdapter()
    publisher = ReportPublisher(adapter=adapter, retry_delays=(0, 0, 0))
    result = _result()
    first = await publisher.publish(result)
    second = await publisher.publish(result)
    assert first["published"] is True
    assert second["published"] is True
    assert "已追加更新版本" in second["message"]
    assert len(adapter.create_calls) == 1  # 只创建一次
    assert len(adapter.update_calls) == 1
    assert "共 2 章" in adapter.update_calls[0][1]


@pytest.mark.asyncio
async def test_publish_chapter_failure_marks_missing() -> None:
    """单章节追加失败 → 标记缺失章节, 不整体回滚, 仍返回发布成功."""
    adapter = _FakeAdapter()
    adapter.append_failures = {"二": RuntimeError("append 失败")}
    resp = await ReportPublisher(adapter=adapter, retry_delays=(0, 0, 0)).publish(_result())
    assert resp["published"] is True
    assert "章节写入缺失: 二" in resp["message"]


# ── MCP 适配器 ──


class _FakeRegistryTool:
    """fake 注册表工具: 固定 ToolResult."""

    def __init__(self, output: Any = None, success: bool = True, error: str | None = None) -> None:
        self._output = output
        self._success = success
        self._error = error

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            tool_name="mcp_feishu_create_doc",
            success=self._success,
            output=self._output,
            error=self._error,
        )


class _FakeRegistry:
    def __init__(self, tools: dict[str, Any] | None = None) -> None:
        self._tools = tools or {}

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)


@pytest.mark.asyncio
async def test_mcp_adapter_calls_registered_tool() -> None:
    """适配器解析 mcp_feishu_* 工具并解析 JSON 输出."""
    tool = _FakeRegistryTool(output='{"doc_token": "d1", "url": "u1"}')
    adapter = McpPublishAdapter(_FakeRegistry({"mcp_feishu_create_doc": tool}))
    resp = await adapter.create_doc("标题")
    assert resp == {"doc_token": "d1", "url": "u1"}


@pytest.mark.asyncio
async def test_mcp_adapter_tool_missing_raises() -> None:
    """工具未注册(server 不可用) → 抛可读错误."""
    adapter = McpPublishAdapter(_FakeRegistry({}))
    with pytest.raises(RuntimeError, match="未注册"):
        await adapter.create_doc("标题")


@pytest.mark.asyncio
async def test_mcp_adapter_tool_failure_raises() -> None:
    """工具执行失败 → 抛可读错误(上层降级)."""
    tool = _FakeRegistryTool(success=False, error="飞书 API 错误")
    adapter = McpPublishAdapter(_FakeRegistry({"mcp_feishu_create_doc": tool}))
    with pytest.raises(RuntimeError, match="飞书 API 错误"):
        await adapter.create_doc("标题")

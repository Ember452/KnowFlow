"""飞书云文档 MCP Server(自建兜底) - stdio 协议.

工具: create_doc(创建云文档+标题) / append_to_doc(追加章节) /
update_doc(追加新版本内容, 幂等重发场景). 内部直接调飞书开放平台 docx OpenAPI
(httpx, 不引入 lark SDK 依赖), 凭证经环境变量 APP_ID/APP_SECRET/USER_ACCESS_TOKEN
注入(McpGateway env 透传). 凭证缺失/API 失败时工具执行返回错误, 由注册链路降级.

官方 server 可用时优先接入官方 lark-openapi-mcp(决策见 docs/adr/0009), 本 server
为无 Node 环境或官方工具名不确定时的兜底实现.
"""

import asyncio
import json
import os

import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer(name="knowflow-feishu", version="0.1.0")

_BASE = "https://open.feishu.cn/open-apis"
_REQUEST_TIMEOUT = 30.0

# 云文档块类型: 2=text, 3=heading1(与飞书 docx API block_type 定义一致)


def _headers() -> dict[str, str]:
    """构造认证请求头; 凭证缺失抛错(由调用方降级)."""
    token = os.environ.get("USER_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("飞书用户凭证缺失: 需配置 USER_ACCESS_TOKEN 环境变量")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _text_block(content: str) -> dict[str, object]:
    """文本块."""
    return {
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": content}}]},
    }


def _heading_block(content: str) -> dict[str, object]:
    """一级标题块."""
    return {
        "block_type": 3,
        "heading1": {"elements": [{"text_run": {"content": content}}]},
    }


async def _post(path: str, body: dict[str, object] | None = None) -> dict[str, object]:
    """调用飞书 OpenAPI; HTTP/业务错误统一抛 RuntimeError(可读信息)."""
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(f"{_BASE}{path}", headers=_headers(), json=body or {})
    if resp.status_code >= 400:
        raise RuntimeError(f"飞书 API 请求失败({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"飞书 API 错误({data.get('code')}): {data.get('msg', '')}")
    return data.get("data", {}) or {}


@server.tool()
async def create_doc(title: str, content: str = "") -> str:
    """创建飞书云文档(标题 + 可选正文), 返回 JSON 含 doc_token 与 url."""
    data = await _post("/docx/v1/documents", {})
    doc_id = str(data.get("document_id", ""))
    url = str(data.get("url", ""))
    blocks: list[dict[str, object]] = [_heading_block(title)]
    if content:
        blocks.append(_text_block(content))
    await _post(f"/docx/v1/documents/{doc_id}/blocks/0/children", {"children": blocks})
    return json.dumps({"doc_token": doc_id, "url": url, "title": title}, ensure_ascii=False)


@server.tool()
async def append_to_doc(doc_token: str, content: str) -> str:
    """向飞书云文档末尾追加文本(章节写入), 返回追加状态."""
    await _post(
        f"/docx/v1/documents/{doc_token}/blocks/0/children",
        {"children": [_text_block(content)]},
    )
    return json.dumps({"doc_token": doc_token, "appended": True}, ensure_ascii=False)


@server.tool()
async def update_doc(doc_token: str, content: str, title: str = "") -> str:
    """更新飞书云文档: 追加【更新】版本(幂等重发场景), 返回更新状态."""
    prefix = f"【更新】{title}" if title else "【更新】"
    blocks: list[dict[str, object]] = [_heading_block(prefix), _text_block(content)]
    await _post(
        f"/docx/v1/documents/{doc_token}/blocks/0/children",
        {"children": blocks},
    )
    return json.dumps({"doc_token": doc_token, "updated": True}, ensure_ascii=False)


def main() -> None:
    """stdio 模式启动入口(子进程方式被 McpGateway 拉起)."""
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()

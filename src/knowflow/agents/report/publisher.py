"""报告发布器 - 报告 → 飞书云文档(经 MCP 工具), 带幂等/重试/降级容错.

容错设计(与设计文档 5.5 一致):
- 重试: create_doc 失败指数退避重试 3 次(1s/3s/9s), 凭证错误不重试;
- 幂等: run_id→doc_token 映射(进程内), 重复 publish 走 update_doc 追加新版本;
- 凭证可读: token 过期/权限不足识别为"请重新授权飞书", 不抛堆栈;
- 部分失败: 单章节追加失败标记缺失章节, 不整体回滚;
- 降级闭环: 发布失败返回可读错误, 报告仍可从沙盒获取.
"""

import asyncio
import json
from typing import Any, Protocol

from knowflow.agents.report.models import ReportResult
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_RETRY_DELAYS = (1, 3, 9)  # 指数退避: 首次直接尝试, 失败后 1s/3s/9s 重试
_CREDENTIAL_HINTS = ("token", "凭证", "权限", "授权", "99991663", "invalid_token")


class PublishAdapter(Protocol):
    """飞书发布适配接口(单测注入 fake)."""

    async def create_doc(self, title: str, content: str = "") -> dict[str, Any]: ...
    async def append_to_doc(self, doc_token: str, content: str) -> dict[str, Any]: ...
    async def update_doc(self, doc_token: str, content: str, title: str = "") -> dict[str, Any]: ...


class McpPublishAdapter:
    """默认适配器: 从 ToolRegistry 解析 mcp_feishu_* 工具调用.

    工具命名约定与 register_mcp_server 一致: mcp_{server_id}_{tool_name}.
    """

    def __init__(self, registry: Any, server_id: str = "feishu") -> None:
        self._registry = registry
        self._server_id = server_id

    async def _call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        name = f"mcp_{self._server_id}_{tool}"
        tool_obj = self._registry.get(name)
        if tool_obj is None:
            raise RuntimeError(f"飞书工具未注册: {name}(MCP server 不可用)")
        result = await tool_obj.execute(**kwargs)
        if not result.success:
            raise RuntimeError(result.error or f"{name} 调用失败")
        output = result.output
        if isinstance(output, str):
            try:
                data: dict[str, Any] = json.loads(output)
                return data
            except json.JSONDecodeError:
                return {"output": output}
        if isinstance(output, dict):
            return {str(k): v for k, v in output.items()}
        return {"output": output}

    async def create_doc(self, title: str, content: str = "") -> dict[str, Any]:
        return await self._call("create_doc", title=title, content=content)

    async def append_to_doc(self, doc_token: str, content: str) -> dict[str, Any]:
        return await self._call("append_to_doc", doc_token=doc_token, content=content)

    async def update_doc(self, doc_token: str, content: str, title: str = "") -> dict[str, Any]:
        return await self._call("update_doc", doc_token=doc_token, content=content, title=title)


class ReportPublisher:
    """报告发布器: 创建文档 → 分章节追加 → 返回文档链接."""

    def __init__(
        self,
        adapter: PublishAdapter | None = None,
        settings: Settings | None = None,
        retry_delays: tuple[float, ...] | None = None,
    ) -> None:
        self._adapter = adapter
        self._settings = settings or get_settings()
        self._retry_delays = retry_delays if retry_delays is not None else _RETRY_DELAYS
        self._doc_tokens: dict[str, str] = {}  # run_id → doc_token(幂等映射)

    async def publish(self, result: ReportResult) -> dict[str, Any]:
        """发布报告到飞书; 成功/降级均返回可读结果(不抛出)."""
        adapter = self._adapter
        if adapter is None:
            return {"published": False, "message": "发布适配器未配置(飞书 MCP 未接入)"}
        try:
            doc_token = self._doc_tokens.get(result.run_id)
            if doc_token is None:
                doc_token = await self._create_with_retry(adapter, result)
                self._doc_tokens[result.run_id] = doc_token
                url = self._doc_url(doc_token)
                missing = await self._append_chapters(adapter, doc_token, result)
                if missing:
                    return {
                        "published": True,
                        "doc_url": url,
                        "message": f"已发布, 章节写入缺失: {', '.join(missing)}",
                    }
                return {"published": True, "doc_url": url, "message": "发布成功"}
            # 幂等重发: 已创建过 → 追加新版本内容(update_doc)
            await adapter.update_doc(
                doc_token, self._render_summary(result), title=result.spec.title
            )
            return {
                "published": True,
                "doc_url": self._doc_url(doc_token),
                "message": "文档已存在, 已追加更新版本",
            }
        except Exception as exc:
            message = str(exc)
            if self._is_credential_error(message):
                logger.warning("report.publish_credential_error", run_id=result.run_id)
                return {
                    "published": False,
                    "message": "发布失败: 飞书凭证无效或已过期, 请重新授权飞书",
                }
            logger.warning("report.publish_failed", run_id=result.run_id, error=message)
            return {"published": False, "message": f"发布失败: {message[:200]}"}

    # ── 内部流程 ──

    async def _create_with_retry(self, adapter: PublishAdapter, result: ReportResult) -> str:
        """创建文档; 指数退避重试 3 次, 凭证错误直接失败(不重试)."""
        last_exc: Exception | None = None
        for delay in (0, *self._retry_delays):
            try:
                resp = await adapter.create_doc(result.spec.title)
                token = str(resp.get("doc_token") or resp.get("document_id") or "")
                if not token:
                    raise RuntimeError(f"创建飞书文档返回为空: {resp}")
                return token
            except Exception as exc:
                last_exc = exc
                if self._is_credential_error(str(exc)):
                    raise
                if delay:
                    logger.warning("report.publish_retry", delay=delay, error=str(exc))
                    await asyncio.sleep(delay)
        raise RuntimeError(f"创建飞书文档失败(重试 3 次后): {last_exc}")

    async def _append_chapters(
        self, adapter: PublishAdapter, doc_token: str, result: ReportResult
    ) -> list[str]:
        """分章节追加写入; 单章失败标记缺失章节, 不整体回滚."""
        missing: list[str] = []
        for ch in result.chapters:
            content = f"## {ch.title}\n\n{ch.body}"
            try:
                await adapter.append_to_doc(doc_token, content)
            except Exception as exc:
                logger.warning("report.publish_chapter_failed", chapter=ch.title, error=str(exc))
                missing.append(ch.title)
        return missing

    @staticmethod
    def _render_summary(result: ReportResult) -> str:
        """幂等重发时的更新摘要(章节数/状态概览)."""
        return (
            f"共 {len(result.chapters)} 章, 证据 {len(result.evidence)} 条, "
            f"审查{'通过' if result.review and result.review.passed else '未完全通过'}"
        )

    @staticmethod
    def _doc_url(doc_token: str) -> str:
        """飞书云文档链接."""
        return f"https://feishu.cn/docx/{doc_token}"

    @staticmethod
    def _is_credential_error(message: str) -> bool:
        """识别凭证/token 错误(返回可读提示, 不重试)."""
        lowered = message.lower()
        return any(hint in lowered for hint in _CREDENTIAL_HINTS)

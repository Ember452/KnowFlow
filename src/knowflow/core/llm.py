"""LLM 客户端懒加载单例 - 对话链路共用的 ChatOpenAI 工厂.

进程内单例, 首次调用 get_chat_llm() 时按 Settings 构造, 避免应用启动即连外部 API;
应用关闭或单测 reset 时通过 dispose_chat_llm() 释放. 单测可 set_chat_llm() 注入 fake.
"""

from typing import Any

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_chat_llm: Any = None


def get_chat_llm() -> Any:
    """获取 ChatOpenAI 单例(懒加载), 支持 ainvoke/astream 异步调用."""
    global _chat_llm
    if _chat_llm is None:
        # 延迟导入: 避免模块加载时初始化 langchain 客户端
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        settings = get_settings()
        _chat_llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=SecretStr(settings.llm_api_key),
            base_url=settings.llm_base_url,
            temperature=0.3,  # 问答适度随机, 兼顾稳定与多样性
            streaming=True,  # 同步路径也走流式后聚合, 保证 astream 可用
        )
        logger.info("llm.initialized", model=settings.llm_model)
    return _chat_llm


def set_chat_llm(llm: Any) -> None:
    """注入 LLM 实例(单测用)."""
    global _chat_llm
    _chat_llm = llm


def dispose_chat_llm() -> None:
    """释放单例(单测 reset 与应用关闭时调用)."""
    global _chat_llm
    _chat_llm = None

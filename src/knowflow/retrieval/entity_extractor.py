"""LLM 实体关系抽取 - 调 ChatOpenAI 输出 JSON, 解析为 Entity/Relation 数据类.

抽取失败重试 2 次, 仍失败返回空结果(不阻塞索引) + warning 日志.
单测通过构造时注入 fake llm 绕过真实 API 调用.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

# LLM 返回 JSON 中常见的代码块包裹, 提取前剥离
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

# 最大重试次数(初次 + 2 次重试 = 共 3 次调用)
_MAX_RETRIES = 2

# 抽取 prompt 模板: 要求 LLM 严格输出 JSON, 附 schema 示例
_PROMPT_TEMPLATE = """请从以下文本中抽取命名实体与实体间关系, 严格输出 JSON, 不要包含任何解释文字.

JSON Schema:
{{
  "entities": [
    {{"name": "实体名称", "type": "person|org|product|system|process|location|other"}}
  ],
  "relations": [
    {{
      "source": "源实体名称",
      "target": "目标实体名称",
      "relation_type": "belongs_to|part_of|related_to|uses|located_in|other"
    }}
  ]
}}

要求:
1. 实体名称保留原文形式(不归一化), 不要拼接修饰词
2. 关系的 source/target 必须是 entities 中已出现的 name
3. 无实体或无关系时返回空数组
4. 仅输出 JSON, 不要 markdown 代码块, 不要解释

文本:
{chunk_text}
"""


@dataclass(frozen=True)
class Entity:
    """抽取的实体."""

    name: str
    type: str
    normalized: str = ""  # normalize() 填充


@dataclass(frozen=True)
class Relation:
    """抽取的关系(实体间有向边)."""

    source: str  # 源实体 name
    target: str  # 目标实体 name
    relation_type: str


@dataclass(frozen=True)
class ExtractResult:
    """一次抽取的结果."""

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


class EntityExtractor:
    """LLM 实体关系抽取器.

    构造时注入 llm(实现 invoke 方法, 返回带 content 属性的对象).
    单测可传 fake llm 绕过真实 API.
    """

    def __init__(self, llm: Any | None = None, *, max_retries: int = _MAX_RETRIES) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake(实现 invoke). None 时懒加载 ChatOpenAI.
            max_retries: JSON 解析失败重试次数, 默认 2.
        """
        self._llm: Any | None = llm
        self._max_retries = max_retries

    def _get_llm(self) -> Any:
        """懒加载 ChatOpenAI(首次调用时)."""
        if self._llm is not None:
            return self._llm
        # 延迟导入: 避免模块加载时连 OpenAI
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        from knowflow.core.config import get_settings

        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=SecretStr(settings.llm_api_key),
            base_url=settings.llm_base_url,
            temperature=0.0,  # 抽取任务用确定性输出
        )
        return self._llm

    def extract(self, chunk_text: str) -> ExtractResult:
        """从 chunk 文本抽取实体与关系.

        Args:
            chunk_text: 已分块的纯文本.

        Returns:
            ExtractResult, 解析失败时返回空结果(不抛异常, 不阻塞索引).
        """
        if not chunk_text or not chunk_text.strip():
            return ExtractResult()

        prompt = _PROMPT_TEMPLATE.format(chunk_text=chunk_text)
        llm = self._get_llm()

        last_error: str = ""
        for attempt in range(self._max_retries + 1):
            try:
                response = llm.invoke(prompt)
                content = _extract_content(response)
                result = _parse_json(content)
                entities = self.normalize([Entity(**e) for e in result.get("entities", [])])
                relations = [Relation(**r) for r in result.get("relations", [])]
                return ExtractResult(entities=entities, relations=relations)
            except (ValueError, KeyError, TypeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "entity_extractor.parse_failed",
                    attempt=attempt + 1,
                    max_retries=self._max_retries + 1,
                    error=last_error,
                )

        # 全部重试失败, 降级返回空结果
        logger.warning(
            "entity_extractor.degraded",
            reason="all retries exhausted",
            last_error=last_error,
        )
        return ExtractResult()

    @staticmethod
    def normalize(entities: list[Entity]) -> list[Entity]:
        """实体归一化: name 去首尾空白, normalized 字段填小写形式.

        Args:
            entities: 原始实体列表.

        Returns:
            归一化后的实体列表(去重, 同 normalized 保留首个).
        """
        seen: set[str] = set()
        result: list[Entity] = []
        for e in entities:
            name = e.name.strip()
            if not name:
                continue
            normalized = name.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(Entity(name=name, type=e.type, normalized=normalized))
        return result


def _extract_content(response: object) -> str:
    """从 LLM 响应中提取文本内容.

    兼容 langchain AIMessage(content=str) 与 fake 返回 str.
    """
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if content is None:
        raise ValueError(f"LLM 响应无 content 属性: {type(response)}")
    return str(content)


def _parse_json(content: str) -> dict:
    """解析 LLM 输出为 JSON dict.

    先剥离 markdown 代码块包裹, 再 json.loads. 失败抛 ValueError.
    """
    if not content or not content.strip():
        raise ValueError("LLM 输出为空")

    # 剥离 ```json ... ``` 代码块
    match = _CODE_BLOCK_RE.search(content)
    if match:
        content = match.group(1)

    # 容错: 截取首个 { 到最后一个 }
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM 输出未找到 JSON 对象: {content[:100]}")
    content = content[start : end + 1]

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {exc}; content={content[:100]}") from exc

    if not isinstance(result, dict):
        raise ValueError(f"JSON 顶层不是对象: {type(result)}")
    return result

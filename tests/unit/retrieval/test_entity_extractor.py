"""entity_extractor 单测 - JSON 解析 / 重试 / 归一 / 降级."""

from dataclasses import dataclass

from knowflow.retrieval.entity_extractor import (
    Entity,
    EntityExtractor,
    ExtractResult,
    _parse_json,
)


@dataclass
class FakeMessage:
    """模拟 langchain AIMessage."""

    content: str


class FakeLLM:
    """fake LLM: 按预设序列返回内容, 记录调用次数."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> FakeMessage:
        self.prompts.append(prompt)
        idx = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        return FakeMessage(content=self.responses[idx])


# ── _parse_json 单测 ──


def test_parse_json_plain() -> None:
    """纯 JSON 字符串解析."""
    result = _parse_json('{"entities": [], "relations": []}')
    assert result == {"entities": [], "relations": []}


def test_parse_json_code_block() -> None:
    """markdown 代码块包裹的 JSON 解析."""
    content = '```json\n{"entities": [{"name": "x", "type": "person"}]}\n```'
    result = _parse_json(content)
    assert len(result["entities"]) == 1


def test_parse_json_with_prefix() -> None:
    """LLM 输出含前缀文字时, 截取 JSON 段."""
    content = '好的, 结果如下:\n{"entities": [], "relations": []}\n以上是结果.'
    result = _parse_json(content)
    assert "entities" in result


def test_parse_json_empty_raises() -> None:
    """空输入抛 ValueError."""
    import pytest

    with pytest.raises(ValueError):
        _parse_json("")


def test_parse_json_invalid_raises() -> None:
    """非法 JSON 抛 ValueError."""
    import pytest

    with pytest.raises(ValueError):
        _parse_json("{invalid json}")


# ── EntityExtractor.extract 单测 ──


def test_extract_normal() -> None:
    """正常 JSON 输出解析为 entities + relations."""
    response = """
    {
      "entities": [
        {"name": "张三", "type": "person"},
        {"name": "财务部", "type": "org"}
      ],
      "relations": [
        {"source": "张三", "target": "财务部", "relation_type": "belongs_to"}
      ]
    }
    """
    llm = FakeLLM([response])
    extractor = EntityExtractor(llm=llm)
    result = extractor.extract("张三在财务部工作")

    assert isinstance(result, ExtractResult)
    assert len(result.entities) == 2
    assert result.entities[0].name == "张三"
    assert result.entities[0].type == "person"
    assert result.entities[0].normalized == "张三"
    assert result.entities[1].name == "财务部"
    assert result.entities[1].normalized == "财务部"
    assert len(result.relations) == 1
    assert result.relations[0].source == "张三"
    assert result.relations[0].target == "财务部"
    assert result.relations[0].relation_type == "belongs_to"
    assert llm.call_count == 1


def test_extract_empty_text() -> None:
    """空文本直接返回空结果, 不调 LLM."""
    llm = FakeLLM([])
    extractor = EntityExtractor(llm=llm)
    result = extractor.extract("")
    assert result.entities == []
    assert result.relations == []
    assert llm.call_count == 0


def test_extract_whitespace_only() -> None:
    """纯空白文本直接返回空结果."""
    llm = FakeLLM([])
    extractor = EntityExtractor(llm=llm)
    result = extractor.extract("   \n\n  ")
    assert result.entities == []
    assert llm.call_count == 0


def test_extract_retry_on_invalid_json() -> None:
    """JSON 解析失败时重试, 第二次成功."""
    invalid = "这不是 JSON"
    valid = '{"entities": [{"name": "李四", "type": "person"}], "relations": []}'
    llm = FakeLLM([invalid, valid])
    extractor = EntityExtractor(llm=llm, max_retries=2)
    result = extractor.extract("李四")

    assert len(result.entities) == 1
    assert result.entities[0].name == "李四"
    assert llm.call_count == 2  # 第一次失败, 第二次成功


def test_extract_degraded_after_max_retries() -> None:
    """超过最大重试次数后降级返回空结果."""
    llm = FakeLLM(["invalid", "still invalid", "nope"])
    extractor = EntityExtractor(llm=llm, max_retries=2)
    result = extractor.extract("some text")

    assert result.entities == []
    assert result.relations == []
    # 初次 + 2 次重试 = 3 次调用
    assert llm.call_count == 3


def test_extract_no_entities_no_relations() -> None:
    """LLM 返回空数组的正常情况."""
    response = '{"entities": [], "relations": []}'
    llm = FakeLLM([response])
    extractor = EntityExtractor(llm=llm)
    result = extractor.extract("无实体的文本")
    assert result.entities == []
    assert result.relations == []


# ── EntityExtractor.normalize 单测 ──


def test_normalize_strips_whitespace() -> None:
    """name 前后空白被剥离."""
    entities = [Entity(name="  张三  ", type="person")]
    result = EntityExtractor.normalize(entities)
    assert result[0].name == "张三"
    assert result[0].normalized == "张三"


def test_normalize_lowercases() -> None:
    """normalized 字段为小写形式."""
    entities = [Entity(name="OpenAI", type="org")]
    result = EntityExtractor.normalize(entities)
    assert result[0].name == "OpenAI"  # name 保留原形
    assert result[0].normalized == "openai"


def test_normalize_dedupes_by_normalized() -> None:
    """同 normalized 的实体去重, 保留首个."""
    entities = [
        Entity(name="OpenAI", type="org"),
        Entity(name="openai", type="org"),  # 同 normalized
        Entity(name="Google", type="org"),
    ]
    result = EntityExtractor.normalize(entities)
    assert len(result) == 2
    assert result[0].name == "OpenAI"
    assert result[1].name == "Google"


def test_normalize_skips_empty_name() -> None:
    """空 name 或纯空白 name 被跳过."""
    entities = [
        Entity(name="", type="person"),
        Entity(name="   ", type="person"),
        Entity(name="张三", type="person"),
    ]
    result = EntityExtractor.normalize(entities)
    assert len(result) == 1
    assert result[0].name == "张三"


def test_normalize_empty_input() -> None:
    """空列表输入返回空列表."""
    assert EntityExtractor.normalize([]) == []


def test_extract_with_code_block_response() -> None:
    """LLM 返回 markdown 代码块包裹的 JSON 也能解析."""
    response = '```json\n{"entities": [{"name": "王五", "type": "person"}], "relations": []}\n```'
    llm = FakeLLM([response])
    extractor = EntityExtractor(llm=llm)
    result = extractor.extract("王五是员工")
    assert len(result.entities) == 1
    assert result.entities[0].name == "王五"

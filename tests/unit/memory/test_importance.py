"""重要性打分单测 - LLM 解析与规则兜底."""

from knowflow.memory.importance import ImportanceScorer
from tests.fakes import FakeChatLLM


def test_rule_score_high_keywords() -> None:
    """偏好/习惯类关键词高置信."""
    assert ImportanceScorer.rule_score("请记住我喜欢用 Markdown 写文档") == 9.0


def test_rule_score_mid_keywords() -> None:
    """身份/目标类中置信."""
    assert ImportanceScorer.rule_score("我是财务部的员工") == 6.0


def test_rule_score_low_default() -> None:
    """普通寒暄低置信."""
    assert ImportanceScorer.rule_score("你好") == 2.0


def test_rule_score_length_bonus() -> None:
    """长消息加分(上限 10)."""
    long_text = "我偏好使用简洁的回答风格" + "补充说明" * 30
    assert ImportanceScorer.rule_score(long_text) > 9.0


async def test_llm_score_parsed() -> None:
    """LLM 返回 JSON 分数被解析."""
    llm = FakeChatLLM(answer='{"importance": 8}')
    assert await ImportanceScorer(llm).score("我喜欢喝咖啡") == 8.0


async def test_llm_failure_falls_back_to_rule() -> None:
    """LLM 失败时回退规则打分."""

    class _BoomLLM:
        async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
            raise RuntimeError("llm down")

    assert await ImportanceScorer(_BoomLLM()).score("我喜欢喝咖啡") == 9.0


async def test_no_llm_uses_rule() -> None:
    """无 LLM 注入时直接规则打分."""
    scorer = ImportanceScorer()
    assert await scorer.score("请记住我的部门是财务") == 9.0
    assert await scorer.score("") == 0.0

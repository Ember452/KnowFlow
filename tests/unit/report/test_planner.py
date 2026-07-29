"""报告规划器单测 - 大纲 JSON 解析/非法回退/LLM 异常回退."""

import pytest

from knowflow.agents.report.planner import Planner, _parse_spec


class _FakeLLM:
    """可脚本化 fake LLM: 固定响应或抛错."""

    def __init__(self, response: str = "", raise_error: bool = False) -> None:
        self._response = response
        self._raise_error = raise_error
        self.invoke_calls = 0

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        self.invoke_calls += 1
        if self._raise_error:
            raise RuntimeError("llm down")
        return self._response


def test_parse_spec_valid_json() -> None:
    """合法 JSON 大纲解析为 ReportSpec."""
    text = '{"title": "报告", "chapters": [{"title": "一", "queries": ["q1", "q2"]}]}'
    spec = _parse_spec(text)
    assert spec is not None
    assert spec.title == "报告"
    assert spec.chapters == ["一"]
    assert spec.research_plan[0].queries == ["q1", "q2"]


def test_parse_spec_invalid_returns_none() -> None:
    """非 JSON/结构缺失/章节为空均返回 None(触发回退)."""
    assert _parse_spec("不是 JSON") is None
    assert _parse_spec('{"title": ""}') is None
    assert _parse_spec('{"title": "t", "chapters": []}') is None
    assert _parse_spec('{"title": "t", "chapters": [{"title": "", "queries": ["q"]}]}') is None


@pytest.mark.asyncio
async def test_plan_uses_llm_spec() -> None:
    """LLM 返回合法大纲时采用该大纲."""
    llm = _FakeLLM('{"title": "T", "chapters": [{"title": "C", "queries": ["q"]}]}')
    spec = await Planner(llm=llm).plan("需求")
    assert spec.title == "T"
    assert spec.chapters == ["C"]
    assert llm.invoke_calls == 1


@pytest.mark.asyncio
async def test_plan_falls_back_on_invalid_json() -> None:
    """非法输出回退默认大纲(标题取需求, 单章节 3 查询)."""
    llm = _FakeLLM("无意义输出")
    spec = await Planner(llm=llm).plan("总结报销制度")
    assert spec.title == "总结报销制度"
    assert len(spec.chapters) == 1
    assert len(spec.research_plan[0].queries) == 3


@pytest.mark.asyncio
async def test_plan_falls_back_on_llm_error() -> None:
    """LLM 异常回退默认大纲(流水线不中断)."""
    llm = _FakeLLM(raise_error=True)
    spec = await Planner(llm=llm).plan("需求")
    assert len(spec.chapters) == 1
    assert llm.invoke_calls == 1

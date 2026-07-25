"""工具编排器单测 - Skill 激活/可见性/工具调用循环/越权拦截/轮数上限.

用 FakeToolCallingLLM(脚本化响应) + CalculatorTool(direct 域恒可见) 验证:
- 无可见工具时 no_tools 短路
- 单轮工具调用 → 结果回填 → 最终答案
- 无需工具时直接返回 content
- 越权调用被拦截但循环不中断
- 达到 max_tool_rounds 时 truncated=True
- 指标被记录
"""

from knowflow.core.config import Settings
from knowflow.services.tool_orchestrator import ToolOrchestrator
from knowflow.tools.builtin.calculator import CalculatorTool
from knowflow.tools.builtin.retrieval_tool import RetrievalTool
from knowflow.tools.builtin.search_tool import SearchTool
from knowflow.tools.domain import AgentRole
from knowflow.tools.metrics import ToolMetrics
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_manager import SkillManager
from tests.fakes import FakeRetriever, FakeToolCallingLLM, _ScriptedResponse


def _build_registry() -> ToolRegistry:
    """构造含 calculator(direct) + retrieval(direct) + search(subagent_only) 的注册表."""
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(RetrievalTool(FakeRetriever()))
    reg.register(SearchTool())
    return reg


def _empty_skill_manager() -> SkillManager:
    """空 Skill 目录的 manager(无激活 Skill, 仅 direct 工具可见)."""
    import tempfile
    from pathlib import Path

    empty_dir = Path(tempfile.mkdtemp())
    return SkillManager(skills_dir=empty_dir)


# ── 无可见工具短路 ──


async def test_no_visible_tools_returns_empty() -> None:
    """主 Agent 无激活 Skill 且无 direct 工具时, no_tools=True."""
    # 空 registry + 空 skills → 无可见工具
    orchestrator = ToolOrchestrator(
        registry=ToolRegistry(),
        skill_manager=_empty_skill_manager(),
        llm=FakeToolCallingLLM([]),
    )
    result = await orchestrator.run("hello")
    assert result.no_tools is True
    assert result.answer == ""
    assert result.tool_calls == []


# ── 单轮工具调用 ──


async def test_single_tool_call_then_answer() -> None:
    """LLM 先调 calculator 求值, 回填后返回最终答案."""
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[{"name": "calculator", "args": {"expression": "2**10"}, "id": "c1"}]
            ),
            _ScriptedResponse(content="2 的 10 次方等于 1024"),
        ]
    )
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    result = await orchestrator.run("帮我算 2 的 10 次方")
    assert result.no_tools is False
    assert "1024" in result.answer
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "calculator"
    assert result.tool_calls[0].success is True
    assert result.tool_calls[0].output == 1024
    assert result.rounds == 1  # 第 1 轮调用工具, 第 2 轮返回答案(round_idx=1)
    # bind_tools 被调用, 注入了可见工具
    assert len(llm.bound_tools) >= 1


# ── 无需工具直接回答 ──


async def test_no_tool_call_direct_answer() -> None:
    """LLM 不调用工具时直接返回 content."""
    llm = FakeToolCallingLLM([_ScriptedResponse(content="你好, 我是 KnowFlow 助手.")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    result = await orchestrator.run("你好")
    assert result.answer == "你好, 我是 KnowFlow 助手."
    assert result.tool_calls == []
    assert result.rounds == 0


# ── 自定义 system prompt 与角色工具清单 ──


async def test_system_prompt_override() -> None:
    """传入 system_prompt 时优先使用, 不再拼接默认检索上下文."""
    llm = FakeToolCallingLLM([_ScriptedResponse(content="子任务结果")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    result = await orchestrator.run("任务", system_prompt="你是子 Agent, 只围绕任务执行")
    assert result.answer == "子任务结果"
    system = str(llm.last_messages[0]["content"])
    assert "你是子 Agent" in system
    assert "检索上下文" not in system


async def test_system_prompt_none_keeps_default_with_context() -> None:
    """未传 system_prompt 时保持默认行为: context 注入 system prompt."""
    llm = FakeToolCallingLLM([_ScriptedResponse(content="回答")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    await orchestrator.run("任务", context="预检索资料")
    system = str(llm.last_messages[0]["content"])
    assert "预检索资料" in system


async def test_visible_tools_text_by_role() -> None:
    """visible_tools_text: 子 Agent 含 subagent_only 域, 主 Agent 不含."""
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=FakeToolCallingLLM([]),
    )
    sub_text = orchestrator.visible_tools_text(AgentRole.SUBAGENT)
    assert "calculator" in sub_text
    assert "search_tool" in sub_text  # subagent_only 域对子 Agent 可见
    main_text = orchestrator.visible_tools_text(AgentRole.MAIN)
    assert "calculator" in main_text
    assert "search_tool" not in main_text  # 主 Agent 不可见 subagent_only 工具


# ── 越权调用被拦截 ──


async def test_permission_denied_continues_loop() -> None:
    """主 Agent 调用 subagent_only 工具被拦截, 记录失败但循环继续到最终答案."""
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[{"name": "search_tool", "args": {"query": "test"}, "id": "s1"}]
            ),
            _ScriptedResponse(content="搜索被拒绝, 无法回答."),
        ]
    )
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    result = await orchestrator.run("帮我搜一下", agent_role=AgentRole.MAIN)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].success is False
    err = result.tool_calls[0].error or ""
    assert "越权" in err or "不可见" in err


# ── 轮数上限 ──


async def test_max_rounds_truncated() -> None:
    """LLM 持续调用工具达到 max_tool_rounds, truncated=True."""
    # 每轮都返回工具调用, 永不给出最终答案
    script = [
        _ScriptedResponse(
            tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": f"c{i}"}]
        )
        for i in range(10)
    ]
    llm = FakeToolCallingLLM(script)
    settings = Settings(env="test", max_tool_rounds=3)
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
        settings=settings,
    )
    result = await orchestrator.run("不停算")
    assert result.truncated is True
    assert result.rounds == 3
    assert len(result.tool_calls) == 3


# ── 指标记录 ──


async def test_metrics_recorded() -> None:
    """工具调用被记入 ToolMetrics."""
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[{"name": "calculator", "args": {"expression": "3*4"}, "id": "c1"}]
            ),
            _ScriptedResponse(content="结果是 12"),
        ]
    )
    metrics = ToolMetrics()
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
        metrics=metrics,
    )
    await orchestrator.run("算 3*4")
    stats = metrics.call_stats()
    assert stats["total_calls"] == 1
    assert stats["success_rate"] == 1.0


# ── 历史注入 ──


async def test_history_injected_into_messages() -> None:
    """history 参数被注入到 LLM 消息序列."""
    llm = FakeToolCallingLLM([_ScriptedResponse(content="好的")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    history = [{"role": "user", "content": "前文"}, {"role": "assistant", "content": "上文回复"}]
    await orchestrator.run("继续", history=history)
    # last_messages 含 system + history(2) + user = 4 条
    assert len(llm.last_messages) == 4
    assert llm.last_messages[1]["content"] == "前文"
    assert llm.last_messages[-1]["content"] == "继续"


# ── 子 Agent 可见 subagent_only 工具 ──


async def test_subagent_can_call_search_tool() -> None:
    """子 Agent 角色 search_tool(subagent_only) 可见且可调用.

    search_tool 未装 duckduckgo 依赖时 execute 返回失败, 但权限校验通过.
    """
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[{"name": "search_tool", "args": {"query": "x"}, "id": "s1"}]
            ),
            _ScriptedResponse(content="搜索完成(实际失败但权限通过)"),
        ]
    )
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    result = await orchestrator.run("搜索", agent_role=AgentRole.SUBAGENT)
    # 权限校验通过(未抛越权), 但 execute 因无依赖失败
    assert len(result.tool_calls) == 1
    # search_tool 权限通过(非越权错误), execute 失败是依赖问题
    assert result.tool_calls[0].error is None or "越权" not in (result.tool_calls[0].error or "")


# ── 检索上下文注入 / 激活集覆盖 / 会话参数自动补全 ──


async def test_context_injected_into_system_prompt() -> None:
    """检索上下文注入 system prompt, 供 LLM 直接引用(无需重复调检索工具)."""
    llm = FakeToolCallingLLM([_ScriptedResponse(content="好的")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    context = "[1] 报销流程: 填写报销单并提交部门审批。"
    await orchestrator.run("报销流程是什么?", context=context)

    system = llm.last_messages[0]["content"]
    assert "检索上下文" in system
    assert context in system


async def test_active_skills_override_visible_tools() -> None:
    """调用方指定 active_skills 时, 仅该 Skill 工具(subagent_only)与 direct 工具可见."""
    from knowflow.core.constants import ExecutionDomain
    from knowflow.tools.skill_schema import SkillDefinition

    review_skill = SkillDefinition(
        name="code_review",
        tools=["search_tool"],
        dependencies=["search_tool"],
        domain=ExecutionDomain.SUBAGENT_ONLY,
    )
    llm = FakeToolCallingLLM([_ScriptedResponse(content="审查完成")])
    orchestrator = ToolOrchestrator(
        registry=_build_registry(),
        skill_manager=_empty_skill_manager(),
        llm=llm,
    )
    await orchestrator.run("审查代码", agent_role=AgentRole.SUBAGENT, active_skills=[review_skill])

    bound_names = {t["function"]["name"] for t in llm.bound_tools}
    assert "search_tool" in bound_names  # 激活 Skill 声明的 subagent_only 工具
    assert "calculator" in bound_names  # direct 域恒可见


async def test_session_id_auto_filled_for_file_tools() -> None:
    """LLM 未提供 session_id 时, 文件类工具自动补当前会话 id(沙盒隔离)."""
    from knowflow.core.constants import ExecutionDomain
    from knowflow.sandbox.workspace import WorkspaceManager
    from knowflow.tools.builtin.file_tools import FileWriteTool
    from knowflow.tools.skill_schema import SkillDefinition
    from tests.fakes import FakeMinio

    reg = ToolRegistry()
    reg.register(FileWriteTool(WorkspaceManager(FakeMinio())))
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[
                    {
                        "id": "1",
                        "name": "file_write_tool",
                        "args": {"path": "/workspace/a.csv", "content": "x"},
                    }
                ]
            ),
            _ScriptedResponse(content="已写入"),
        ]
    )
    analysis_skill = SkillDefinition(
        name="data_analysis",
        tools=["file_write_tool"],
        dependencies=[],
        domain=ExecutionDomain.SKILL_ONLY,
    )
    orchestrator = ToolOrchestrator(registry=reg, skill_manager=_empty_skill_manager(), llm=llm)
    result = await orchestrator.run(
        "把结果存成 CSV", session_id="42", active_skills=[analysis_skill]
    )

    assert result.tool_calls[0].args["session_id"] == "42"
    assert result.tool_calls[0].success is True


async def test_session_id_not_injected_when_none() -> None:
    """未传 session_id 时不自动补参, 工具参数保持 LLM 原样."""
    from knowflow.core.constants import ExecutionDomain
    from knowflow.sandbox.workspace import WorkspaceManager
    from knowflow.tools.builtin.file_tools import FileWriteTool
    from knowflow.tools.skill_schema import SkillDefinition
    from tests.fakes import FakeMinio

    reg = ToolRegistry()
    reg.register(FileWriteTool(WorkspaceManager(FakeMinio())))
    llm = FakeToolCallingLLM(
        [
            _ScriptedResponse(
                tool_calls=[
                    {
                        "id": "1",
                        "name": "file_write_tool",
                        "args": {"path": "/workspace/a.csv", "content": "x"},
                    }
                ]
            ),
            _ScriptedResponse(content="已写入"),
        ]
    )
    analysis_skill = SkillDefinition(
        name="data_analysis",
        tools=["file_write_tool"],
        dependencies=[],
        domain=ExecutionDomain.SKILL_ONLY,
    )
    orchestrator = ToolOrchestrator(registry=reg, skill_manager=_empty_skill_manager(), llm=llm)
    result = await orchestrator.run("把结果存成 CSV", active_skills=[analysis_skill])

    assert "session_id" not in result.tool_calls[0].args

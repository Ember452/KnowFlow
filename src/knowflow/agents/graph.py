"""LangGraph 状态机 - 多 Agent 编排的图定义与条件路由.

节点:
    START → understand(规则意图) → plan(LLM 规划) ─┬─ delegate → execute(并发委派) ─┐
                                                    └─ direct  ──────────────────────┤
                                            summarize(汇总/直答) ←──────────────────┘
                                                                    → END

条件路由: plan 节点输出 needs_delegation, true 走 execute(委派并发执行),
false 直接走 summarize(直答). 编译时挂 checkpoint saver(CheckpointManager),
每个节点边界自动保存状态并维护 parent_checkpoint_id 父子链(断点续跑).
"""

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from knowflow.agents.state import AgentState
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


def _route(state: AgentState) -> str:
    """条件路由: 是否需要委派子 Agent."""
    return "execute" if state.get("needs_delegation") else "summarize"


def build_agent_graph(
    orchestrator: Any,
    checkpointer: Any | None = None,
    node_factory: Callable[[str, Any], Any] | None = None,
) -> Any:
    """构建并编译多 Agent 状态机.

    Args:
        orchestrator: MultiAgentOrchestrator 实例(提供 understand/plan/execute/
            summarize 节点方法).
        checkpointer: BaseCheckpointSaver(CheckpointManager.get_saver() 产出);
            None 时无 checkpoint 能力(测试/降级).
        node_factory: 节点包装工厂(测试注入, 替换节点实现); None 时用默认节点.

    Returns:
        编译后的 CompiledStateGraph.
    """
    node = node_factory or (lambda name, fn: fn)
    graph = StateGraph(AgentState)
    graph.add_node("understand", node("understand", orchestrator.understand_node))
    graph.add_node("plan", node("plan", orchestrator.plan_node))
    graph.add_node("execute", node("execute", orchestrator.execute_node))
    graph.add_node("summarize", node("summarize", orchestrator.summarize_node))
    graph.add_edge(START, "understand")
    graph.add_edge("understand", "plan")
    graph.add_conditional_edges(
        "plan",
        _route,
        {"execute": "execute", "summarize": "summarize"},
    )
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", END)
    compiled = graph.compile(checkpointer=checkpointer)
    logger.debug("agent_graph.compiled", checkpointer=checkpointer is not None)
    return compiled

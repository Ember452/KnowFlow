"""AgentState - LangGraph 状态机共享状态.

字段对齐设计文档 3.4 模块三: messages / tool_calls / subtasks / context_budget /
active_skills. 节点函数返回"部分更新 dict", LangGraph 按 TypedDict 合并进状态.
"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """多 Agent 编排状态机共享状态.

    - query: 用户原始问题
    - intent: understand 节点两级路由结果(simple 直连 / complex 强信号 / uncertain 交 LLM 判断)
    - messages: 主 Agent 对话消息(规划/汇总用)
    - needs_delegation: plan 节点判断是否需要委派子 Agent
    - plan: 规划结果 [{id, task, description}]
    - subtask_results: 子任务执行结果 [{id, success, output, error, latency_ms}]
    - context_budget: 上下文预算 token(子 Agent 上下文隔离用)
    - active_skills: 激活 Skill 名称列表
    - agent_role: 当前角色 main/sub
    - session_id: 会话 id(落库用)
    - run_id: 主 Agent run id(thread_id 关联 checkpoint)
    - retrieval_context: 预检索上下文文本(子 Agent/直答注入)
    - history: 最近对话历史(主 Agent 直答链路保持多轮上下文)
    - final_answer: 最终汇总答案
    """

    query: str
    intent: str
    messages: list[dict[str, Any]]
    needs_delegation: bool
    plan: list[dict[str, Any]]
    subtask_results: list[dict[str, Any]]
    context_budget: int
    active_skills: list[str]
    agent_role: str
    session_id: int | None
    run_id: int | None
    retrieval_context: str
    history: list[dict[str, str]]
    final_answer: str

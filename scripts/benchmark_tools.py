"""benchmark_tools.py - 工具治理指标对比脚本(执行域隔离 vs 全量注入).

静态模式(默认): 不依赖真实 LLM, 用规则意图识别激活 Skill, 统计三项指标:
    1. 可见工具数下降率(全量注入 vs 执行域隔离)
    2. Schema Token 下降率(全量注入 vs 执行域隔离)
    3. FC 准确率(预期工具在可见集中视为可正确调用, 30+ 场景)

真实模式: 需 LLM API Key, 由 ToolOrchestrator 跑真实工具调用循环,
以 LLM 实际调用的工具是否命中预期判定 FC 准确率.

用法:
    uv run python scripts/benchmark_tools.py              # 静态模式(默认)
    uv run python scripts/benchmark_tools.py --mode real  # 真实模式(需 LLM)
    uv run python scripts/benchmark_tools.py --report     # 生成报告到 docs/benchmarks/
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 将 src 加入 sys.path, 支持 `python scripts/benchmark_tools.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowflow.core.constants import ExecutionDomain  # noqa: E402
from knowflow.tools.builtin import build_default_registry  # noqa: E402
from knowflow.tools.domain import AgentRole, filter_skills_by_role  # noqa: E402
from knowflow.tools.injector import Injector  # noqa: E402
from knowflow.tools.metrics import ToolMetrics  # noqa: E402
from knowflow.tools.skill_manager import SkillManager  # noqa: E402
from knowflow.tools.visibility import VisibilityCalculator  # noqa: E402


@dataclass
class Scenario:
    """单条工具调用场景: 查询 + 预期激活 Skill + 预期调用工具 + Agent 角色.

    expected_tool 为 None 表示预期不调用工具(LLM 直接回答即正确).
    """

    query: str
    expected_skill: str | None  # None 表示无需激活 Skill(仅 direct 工具)
    expected_tool: str | None  # None 表示预期不调用工具
    role: AgentRole = AgentRole.MAIN
    keywords: tuple[str, ...] = ()  # 意图识别关键词


@dataclass
class BenchmarkResult:
    """基准对比结果."""

    baseline_visible: float  # 全量注入平均可见工具数
    isolated_visible: float  # 隔离注入平均可见工具数
    visible_reduction_pct: float  # 可见工具数下降率
    baseline_tokens: float  # 全量注入平均 Schema Token
    isolated_tokens: float  # 隔离注入平均 Schema Token
    token_reduction_pct: float  # Token 下降率
    fc_accuracy: float  # FC 准确率
    scenario_count: int
    mode: str = "static"  # static=规则代理判定 / real=真实 LLM 调用判定
    per_scenario: list[dict[str, Any]] = field(default_factory=list)


# ── 30+ 条工具调用场景 ──
# 覆盖 4 个 Skill + direct-only 场景, 主/子 Agent 角色
SCENARIOS: list[Scenario] = [
    # knowledge_qa(检索知识库) - 8 条
    Scenario(
        "公司报销流程是什么?",
        "knowledge_qa",
        "retrieval_tool",
        keywords=("报销", "流程"),
    ),
    Scenario(
        "产品 X 的规格参数",
        "knowledge_qa",
        "retrieval_tool",
        keywords=("规格", "参数", "产品"),
    ),
    Scenario("请介绍一下年假政策", "knowledge_qa", "retrieval_tool", keywords=("年假", "政策")),
    Scenario("IT 故障申报流程", "knowledge_qa", "retrieval_tool", keywords=("故障", "申报", "IT")),
    Scenario("财务报销审批节点", "knowledge_qa", "retrieval_tool", keywords=("财务", "审批")),
    Scenario(
        "产品手册有哪些功能",
        "knowledge_qa",
        "retrieval_tool",
        keywords=("产品", "功能", "手册"),
    ),
    Scenario("运维手册的应急流程", "knowledge_qa", "retrieval_tool", keywords=("运维", "应急")),
    Scenario("HR 入职流程说明", "knowledge_qa", "retrieval_tool", keywords=("HR", "入职")),
    # data_analysis(计算 + 文件) - 10 条
    Scenario("帮我算 2 的 10 次方", "data_analysis", "calculator", keywords=("算", "次方")),
    Scenario(
        "计算 (1200 + 350) * 0.85",
        "data_analysis",
        "calculator",
        keywords=("计算", "*"),
    ),
    Scenario("把计算结果存成 CSV", "data_analysis", "file_write_tool", keywords=("存", "CSV")),
    Scenario(
        "导出分析结果到文件",
        "data_analysis",
        "file_write_tool",
        keywords=("导出", "文件"),
    ),
    Scenario(
        "读取沙盒里的数据文件",
        "data_analysis",
        "file_read_tool",
        keywords=("读取", "数据文件"),
    ),
    Scenario(
        "列出工作区有哪些文件",
        "data_analysis",
        "file_list_tool",
        keywords=("列出", "文件"),
    ),
    Scenario("算一下利润率", "data_analysis", "calculator", keywords=("算", "利润")),
    Scenario(
        "查看 /workspace/result.json",
        "data_analysis",
        "file_read_tool",
        keywords=("查看", "workspace"),
    ),
    Scenario("保存报告为 summary.md", "data_analysis", "file_write_tool", keywords=("保存", "md")),
    Scenario("工作区文件清单", "data_analysis", "file_list_tool", keywords=("文件", "清单")),
    # document_summary(检索 + 写文件) - 6 条
    Scenario(
        "帮我总结产品手册核心功能",
        "document_summary",
        "retrieval_tool",
        keywords=("总结", "产品"),
    ),
    Scenario("概括这份合同的要点", "document_summary", "retrieval_tool", keywords=("概括", "合同")),
    Scenario("把摘要存成文件", "document_summary", "file_write_tool", keywords=("摘要", "存")),
    Scenario(
        "总结运维手册并导出",
        "document_summary",
        "retrieval_tool",
        keywords=("总结", "运维"),
    ),
    Scenario("提取文档关键信息", "document_summary", "retrieval_tool", keywords=("提取", "文档")),
    Scenario(
        "生成结构化摘要文件",
        "document_summary",
        "file_write_tool",
        keywords=("摘要", "文件"),
    ),
    # code_review(子 Agent: 搜索 + 文件读取) - 5 条, subagent 角色
    Scenario(
        "审查 /workspace/snippet.py 的实现",
        "code_review",
        "file_read_tool",
        role=AgentRole.SUBAGENT,
        keywords=("审查", "snippet"),
    ),
    Scenario(
        "这段代码符合最佳实践吗? 查一下规范",
        "code_review",
        "search_tool",
        role=AgentRole.SUBAGENT,
        keywords=("最佳实践", "规范", "查"),
    ),
    Scenario(
        "审查代码并搜索相关 API 文档",
        "code_review",
        "search_tool",
        role=AgentRole.SUBAGENT,
        keywords=("审查", "搜索", "API"),
    ),
    Scenario(
        "读取待审代码文件",
        "code_review",
        "file_read_tool",
        role=AgentRole.SUBAGENT,
        keywords=("读取", "代码文件"),
    ),
    Scenario(
        "查最新框架文档对照实现",
        "code_review",
        "search_tool",
        role=AgentRole.SUBAGENT,
        keywords=("查", "文档", "框架"),
    ),
    # direct-only(无需 Skill) - 4 条; 自我介绍场景预期不调用工具
    Scenario("你好, 自我介绍一下", None, None, keywords=()),
    Scenario("1+1 等于几", None, "calculator", keywords=()),
    Scenario("知识库里有报销流程吗", None, "retrieval_tool", keywords=()),
    Scenario("算 3*7", None, "calculator", keywords=()),
]


def _recognize_skill(query: str, scenario: Scenario) -> str | None:
    """规则意图识别: 按 keyword 匹配激活 Skill. 匹配失败返回 None(仅 direct 可见).

    模拟 LLM 意图识别: 命中关键词则激活 expected_skill, 否则不激活.
    """
    if not scenario.keywords:
        return scenario.expected_skill  # direct-only 场景直接返回
    if any(kw in query for kw in scenario.keywords):
        return scenario.expected_skill
    return None


def _is_fc_correct(scenario: Scenario, tools: set[str], *, real: bool) -> bool:
    """FC 判定: 预期工具是否命中给定工具集.

    静态模式(real=False): 命中可见集即可(注入不阻碍调用的代理指标),
    expected_tool=None 视为恒正确(无需工具).
    真实模式(real=True): expected_tool=None 要求 LLM 实际未调用任何工具,
    否则要求实际调用集中包含预期工具.
    """
    if scenario.expected_tool is None:
        return True if not real else len(tools) == 0
    return scenario.expected_tool in tools


def run_static_benchmark() -> BenchmarkResult:
    """静态模式: 规则意图识别 + 可见性计算, 统计三项指标."""
    from knowflow.sandbox.workspace import WorkspaceManager

    registry = build_default_registry(
        retriever=_FakeRetriever(),
        workspace_manager=WorkspaceManager(_FakeMinio()),
    )
    skill_manager = SkillManager()
    visibility = VisibilityCalculator()
    injector = Injector()
    metrics = ToolMetrics()

    # 全量注入 baseline: 全部非 internal 工具(忽略执行域隔离)
    all_defs = [t.to_def() for t in registry.list_all() if t.domain != ExecutionDomain.INTERNAL]
    baseline_count = len(all_defs)
    baseline_tokens = injector.schema_tokens(all_defs)

    per_scenario: list[dict[str, Any]] = []
    isolated_count_sum = 0
    isolated_token_sum = 0
    fc_correct = 0

    for sc in SCENARIOS:
        # 意图识别 → 激活 Skill
        activated = _recognize_skill(sc.query, sc)
        active_skills = []
        if activated:
            skill_def = skill_manager.get(activated)
            if skill_def and skill_def.enabled:
                active_skills = [skill_def.model_copy(update={"enabled": True})]

        # 按角色过滤
        active_skills = filter_skills_by_role(active_skills, sc.role)

        # 执行域隔离: 计算可见工具
        visible = visibility.compute(active_skills, sc.role, registry)
        isolated_count = len(visible)
        isolated_tokens = injector.schema_tokens(visible)

        isolated_count_sum += isolated_count
        isolated_token_sum += isolated_tokens

        # FC 准确率: 预期工具是否在可见集中(静态代理: 可见即可正确调用)
        visible_names = {t.name for t in visible}
        correct = _is_fc_correct(sc, visible_names, real=False)
        if correct:
            fc_correct += 1

        metrics.snapshot(isolated_count, isolated_tokens, correct, scenario=sc.query[:30])
        per_scenario.append(
            {
                "query": sc.query,
                "role": sc.role.value,
                "activated_skill": activated or "(none)",
                "expected_tool": sc.expected_tool or "(none)",
                "visible_tools": sorted(visible_names),
                "baseline_count": baseline_count,
                "isolated_count": isolated_count,
                "isolated_tokens": isolated_tokens,
                "fc_correct": correct,
            }
        )

    n = len(SCENARIOS)
    avg_isolated_count = isolated_count_sum / n
    avg_isolated_tokens = isolated_token_sum / n
    visible_reduction = (1 - avg_isolated_count / baseline_count) * 100
    token_reduction = (1 - avg_isolated_tokens / baseline_tokens) * 100
    fc_accuracy = fc_correct / n

    return BenchmarkResult(
        baseline_visible=baseline_count,
        isolated_visible=round(avg_isolated_count, 2),
        visible_reduction_pct=round(visible_reduction, 1),
        baseline_tokens=baseline_tokens,
        isolated_tokens=round(avg_isolated_tokens, 2),
        token_reduction_pct=round(token_reduction, 1),
        fc_accuracy=round(fc_accuracy, 4),
        scenario_count=n,
        mode="static",
        per_scenario=per_scenario,
    )


async def run_real_benchmark() -> BenchmarkResult:
    """真实模式: 真实 LLM 经 ToolOrchestrator 跑工具调用循环, 统计真实 FC 准确率.

    可见工具数/Token 下降率与静态模式同源(规则意图识别), FC 准确率由
    LLM 实际调用的工具判定. 需 KNOWFLOW_LLM_API_KEY.
    """
    from knowflow.core.llm import get_chat_llm
    from knowflow.sandbox.workspace import WorkspaceManager
    from knowflow.services.tool_orchestrator import ToolOrchestrator

    llm = get_chat_llm()
    registry = build_default_registry(
        retriever=_FakeRetriever(),
        workspace_manager=WorkspaceManager(_FakeMinio()),
    )
    skill_manager = SkillManager()
    orchestrator = ToolOrchestrator(registry, skill_manager, llm)
    visibility = VisibilityCalculator()
    injector = Injector()

    # 全量注入 baseline(同静态模式)
    all_defs = [t.to_def() for t in registry.list_all() if t.domain != ExecutionDomain.INTERNAL]
    baseline_count = len(all_defs)
    baseline_tokens = injector.schema_tokens(all_defs)

    per_scenario: list[dict[str, Any]] = []
    isolated_count_sum = 0
    isolated_token_sum = 0
    fc_correct = 0
    total = len(SCENARIOS)

    for i, sc in enumerate(SCENARIOS, 1):
        print(f"[{i}/{total}] {sc.query[:40]}")
        activated = _recognize_skill(sc.query, sc)
        active_skills: list[Any] = []
        if activated:
            skill_def = skill_manager.get(activated)
            if skill_def and skill_def.enabled:
                active_skills = [skill_def.model_copy(update={"enabled": True})]
        active_skills = filter_skills_by_role(active_skills, sc.role)

        visible = visibility.compute(active_skills, sc.role, registry)
        isolated_count = len(visible)
        isolated_tokens = injector.schema_tokens(visible)
        isolated_count_sum += isolated_count
        isolated_token_sum += isolated_tokens
        visible_names = {t.name for t in visible}

        # 真实工具调用循环: 注入隔离可见工具, LLM 自主决定是否调用
        result = await orchestrator.run(sc.query, agent_role=sc.role, active_skills=active_skills)
        called = {tc.tool_name for tc in result.tool_calls}
        correct = _is_fc_correct(sc, called, real=True)
        if correct:
            fc_correct += 1
        print(
            f"    called={sorted(called) or '(none)'} expected={sc.expected_tool or '(none)'} "
            f"{'✓' if correct else '✗'}"
        )

        per_scenario.append(
            {
                "query": sc.query,
                "role": sc.role.value,
                "activated_skill": activated or "(none)",
                "expected_tool": sc.expected_tool or "(none)",
                "called_tools": sorted(called),
                "visible_tools": sorted(visible_names),
                "baseline_count": baseline_count,
                "isolated_count": isolated_count,
                "isolated_tokens": isolated_tokens,
                "fc_correct": correct,
            }
        )

    n = len(SCENARIOS)
    avg_isolated_count = isolated_count_sum / n
    avg_isolated_tokens = isolated_token_sum / n
    visible_reduction = (1 - avg_isolated_count / baseline_count) * 100
    token_reduction = (1 - avg_isolated_tokens / baseline_tokens) * 100
    fc_accuracy = fc_correct / n

    return BenchmarkResult(
        baseline_visible=baseline_count,
        isolated_visible=round(avg_isolated_count, 2),
        visible_reduction_pct=round(visible_reduction, 1),
        baseline_tokens=baseline_tokens,
        isolated_tokens=round(avg_isolated_tokens, 2),
        token_reduction_pct=round(token_reduction, 1),
        fc_accuracy=round(fc_accuracy, 4),
        scenario_count=n,
        mode="real",
        per_scenario=per_scenario,
    )


class _FakeRetriever:
    """静态模式用空检索器(不实际检索, 仅占位构造 registry)."""

    async def retrieve(self, query: str, **kwargs: Any) -> Any:
        from dataclasses import dataclass, field

        @dataclass
        class _Result:
            chunks: list = field(default_factory=list)
            query: str = ""
            latency_ms: float = 0.0
            cache_hit: bool = False

        return _Result(chunks=[], query=query)


class _FakeMinio:
    """静态模式用内存 MinIO 桩(仅满足 WorkspaceManager 构造, 不实际读写)."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put_object(
        self, bucket: str, name: str, data: Any, length: int, content_type: str = ""
    ) -> None:
        content = data.read() if hasattr(data, "read") else bytes(data)
        self._objects[name] = content

    def remove_object(self, bucket: str, name: str) -> None:
        self._objects.pop(name, None)

    def get_object(self, bucket: str, name: str) -> Any:
        from io import BytesIO

        return BytesIO(self._objects.get(name, b""))

    def list_objects(
        self, bucket: str, prefix: str | None = None, recursive: bool = False
    ) -> list[Any]:
        names = sorted(self._objects)
        if prefix:
            names = [n for n in names if n.startswith(prefix)]

        class _Obj:
            def __init__(self, name: str, size: int) -> None:
                self.object_name = name
                self.size = size

        return [_Obj(n, len(self._objects[n])) for n in names]

    def stat_object(self, bucket: str, name: str) -> Any:
        class _Stat:
            def __init__(self, name: str, size: int) -> None:
                self.object_name = name
                self.size = size

        if name not in self._objects:
            raise KeyError(name)
        return _Stat(name, len(self._objects[name]))

    def bucket_exists(self, bucket: str) -> bool:
        return True


def _format_report(result: BenchmarkResult) -> str:
    """生成 Markdown 报告."""
    is_real = result.mode == "real"
    lines = [
        "# 工具治理指标对比报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 模式: "
        + ("真实(真实 LLM 工具调用循环)" if is_real else "静态(规则意图识别, 无真实 LLM)"),
        f"> 场景数: {result.scenario_count}",
        "",
        "## 指标总览",
        "",
        "| 指标 | 全量注入(baseline) | 执行域隔离 | 下降率/准确率 | 目标 |",
        "|---|---|---|---|---|",
        f"| 可见工具数(均值) | {result.baseline_visible} | {result.isolated_visible} | "
        f"-{result.visible_reduction_pct}% | -34.2% |",
        f"| Schema Token(均值) | {result.baseline_tokens} | {result.isolated_tokens} | "
        f"-{result.token_reduction_pct}% | -32.6% |",
        f"| FC 准确率 | - | - | {result.fc_accuracy * 100:.1f}% | 94+% |",
        "",
        "## 方法说明",
        "",
        "- **全量注入(baseline)**: 忽略执行域隔离, 将全部非 internal 工具的 JSON Schema "
        "注入 LLM prompt。",
        "- **执行域隔离**: 按意图识别激活对应 Skill, 经 VisibilityCalculator 计算可见工具集"
        "(direct 恒可见 + skill_only 按激活 + subagent_only 按角色 + internal 永不可见)。",
        "- **可见工具数**: 注入给 LLM 的工具定义数量, 越少 prompt 越精简。",
        "- **Schema Token**: 注入 schema 的字符数 / 4 近似 Token 量。",
        f"- **FC 准确率**: {result.scenario_count} 条场景中, "
        + (
            "LLM 实际调用的工具命中预期工具的比例(真实模式, 由 ToolOrchestrator 跑"
            "完整工具调用循环判定); 预期不调用工具的场景要求 LLM 未发起调用。"
            if is_real
            else "预期工具在隔离可见集中的比例(静态模式代理指标; 真实模式由 LLM 实际调用判定)。"
        ),
        "",
        "## 场景明细",
        "",
        "| 查询 | 角色 | 激活 Skill | 预期工具 | 可见工具数 | Token | FC 正确 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in result.per_scenario:
        lines.append(
            f"| {s['query']} | {s['role']} | {s['activated_skill']} | {s['expected_tool']} | "
            f"{s['isolated_count']} | {s['isolated_tokens']} | {'✓' if s['fc_correct'] else '✗'} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"执行域隔离使可见工具数下降 **{result.visible_reduction_pct}%**(目标 34.2%), "
            f"Schema Token 下降 **{result.token_reduction_pct}%**(目标 32.6%), "
            f"FC 准确率 **{result.fc_accuracy * 100:.1f}%**(目标 94+%)。"
            + (
                ""
                if is_real
                else "静态模式用规则意图识别模拟 Skill 激活, 真实模式请运行 "
                "`uv run python scripts/benchmark_tools.py --mode real` 并配置 LLM API Key。"
            ),
            "",
            "> 注: "
            + (
                "真实模式 FC 准确率由真实 LLM 的工具调用判定, 与静态代理指标口径不同, "
                "结果以真实实测为准。"
                if is_real
                else "静态模式 FC 准确率为「预期工具在可见集中」的代理指标, "
                "不等同真实 LLM 调用准确率。真实模式需 LLM API Key, 由 ToolOrchestrator 跑完整"
                "工具调用循环后统计。"
            ),
        ]
    )
    return "\n".join(lines)


def _print_result(result: BenchmarkResult) -> None:
    """控制台输出三项指标(含模式标注)."""
    mode_label = "真实模式" if result.mode == "real" else "静态模式"
    print("═" * 60)
    print(f"工具治理指标对比({mode_label})")
    print("═" * 60)
    print(f"场景数:           {result.scenario_count}")
    print(
        f"可见工具数:       baseline={result.baseline_visible} → "
        f"isolated={result.isolated_visible}"
        f"  (↓{result.visible_reduction_pct}%, 目标 -34.2%)"
    )
    print(
        f"Schema Token:     baseline={result.baseline_tokens} → "
        f"isolated={result.isolated_tokens}"
        f"  (↓{result.token_reduction_pct}%, 目标 -32.6%)"
    )
    print(f"FC 准确率:        {result.fc_accuracy * 100:.1f}%  (目标 94+%)")
    print("═" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="工具治理指标对比脚本")
    parser.add_argument("--mode", choices=["static", "real"], default="static", help="运行模式")
    parser.add_argument("--report", action="store_true", help="生成报告到 docs/benchmarks/")
    args = parser.parse_args()

    if args.mode == "real":
        from knowflow.core.config import get_settings

        if not get_settings().llm_api_key:
            print("真实模式需要 KNOWFLOW_LLM_API_KEY, 请先配置 .env 后重试。")
            sys.exit(1)
        result = asyncio.run(run_real_benchmark())
        _print_result(result)
        if args.report:
            _write_report(result, suffix="_real")
        return

    result = run_static_benchmark()
    _print_result(result)

    if args.report:
        _write_report(result)


def _write_report(result: BenchmarkResult, suffix: str = "") -> None:
    """写指标报告到 docs/benchmarks/."""
    report_dir = ROOT / "docs" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    report_path = report_dir / f"tool_governance_{date_str}{suffix}.md"
    report_path.write_text(_format_report(result), encoding="utf-8")
    print(f"\n报告已生成: {report_path}")


if __name__ == "__main__":
    main()

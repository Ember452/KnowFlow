"""报告流水线数据模型 - 报告规格/证据/章节/审查/结果.

引用溯源规范: 章节正文中的 [n] 引用指向证据包全局下标(从 1 开始),
Reviewer 校验每个 [n] 均可定位到证据(防幻觉), 参考文献表由证据包生成.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class ReportStage(StrEnum):
    """报告流水线阶段."""

    PLANNING = "planning"  # 规划: 大纲 + 检索计划
    RESEARCH = "research"  # 并行调研: 知识库/记忆/联网三源
    SYNTHESIS = "synthesis"  # 证据融合: 去重 + 组织证据包
    WRITING = "writing"  # 分章节并行撰写
    REVIEW = "review"  # 事实核查: 引用真实性 + 结论支持度
    DONE = "done"  # 完成(已落盘)
    FAILED = "failed"  # 失败(返回结构化错误)


class EvidenceSource(StrEnum):
    """证据来源类型."""

    KNOWLEDGE = "knowledge"  # 知识库混合检索
    MEMORY = "memory"  # 长期记忆召回
    WEB = "web"  # 联网搜索


@dataclass(frozen=True)
class Evidence:
    """单条证据(带出处, 供 [n] 引用溯源)."""

    source: EvidenceSource
    content: str
    title: str = ""  # 文档标题/记忆来源/搜索标题
    doc_id: int | None = None  # 知识库文档 id
    url: str = ""  # 联网来源链接
    score: float = 0.0


@dataclass(frozen=True)
class ChapterPlan:
    """章节检索计划: 章节标题 + 检索查询列表."""

    chapter: str
    queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportSpec:
    """报告规格(Planner 产出): 标题 + 章节列表 + 检索计划 + 是否检索决策.

    needs_research 参照 Self-RAG 的 retrieve 决策: 请求是否需要外部信息
    (知识库/记忆/联网)支撑; false 时流水线跳过调研阶段, 直接基于模型知识撰写.
    默认 true(检索兜底, 决策缺失时行为与旧版一致).
    """

    title: str
    chapters: list[str] = field(default_factory=list)
    research_plan: list[ChapterPlan] = field(default_factory=list)
    needs_research: bool = True


@dataclass(frozen=True)
class EvidencePack:
    """证据包: 全局证据列表 + 章节→证据下标映射(供 Writer 注入与 Reviewer 校验)."""

    evidence: list[Evidence] = field(default_factory=list)
    chapter_index: dict[str, list[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class Chapter:
    """报告章节正文."""

    title: str
    body: str = ""


@dataclass(frozen=True)
class ReviewResult:
    """Reviewer 结论: 通过与否 + 问题清单."""

    passed: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class ReportResult:
    """报告产物: 规格 + 证据包 + 章节 + 参考文献 + 审查结论 + 落盘路径."""

    run_id: str
    spec: ReportSpec
    evidence: list[Evidence] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    review: ReviewResult | None = None
    references: list[str] = field(default_factory=list)  # 参考文献表(渲染后文本行)
    markdown_path: str = ""  # 沙盒虚拟路径(落盘失败为空)
    stage: ReportStage = ReportStage.DONE
    error: str | None = None

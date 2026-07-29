"""报告接口 Schema - 创建请求/任务状态/产物/发布响应."""

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    """创建报告任务请求."""

    query: str = Field(min_length=3, max_length=2000, description="报告需求描述")
    session_id: int | None = Field(default=None, description="沙盒会话 id(报告落盘归属)")


class ChapterOut(BaseModel):
    """报告章节(含 [n] 引用标注)."""

    title: str = Field(description="章节标题")
    body: str = Field(description="章节正文(Markdown, 含 [n] 引用标注)")


class EvidenceOut(BaseModel):
    """证据条目(供引用溯源展示)."""

    source: str = Field(description="来源类型: knowledge/memory/web")
    content: str = Field(description="证据内容")
    title: str = Field(default="", description="文档标题/来源标题")
    doc_id: int | None = Field(default=None, description="知识库文档 id")
    url: str = Field(default="", description="联网来源链接")


class ReportOut(BaseModel):
    """报告任务状态(创建/进度查询)."""

    run_id: str
    query: str
    status: str = Field(description="running/completed/failed")
    stage: str = Field(
        description="当前阶段: planning/research/synthesis/writing/review/done/failed"
    )
    detail: str = Field(default="", description="阶段进度说明")
    error: str | None = Field(default=None, description="失败原因")
    markdown_path: str = Field(default="", description="沙盒落盘路径(完成后有值)")
    progress_log: list[dict[str, str]] = Field(
        default_factory=list, description="阶段进度日志(时间序: 阶段/说明/时间戳)"
    )


class ReportResultOut(BaseModel):
    """报告产物(完成后查询)."""

    run_id: str
    title: str
    status: str
    chapters: list[ChapterOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    review_passed: bool = Field(default=False, description="事实核查是否通过")
    issues: list[str] = Field(default_factory=list, description="核查问题清单(未通过时)")
    markdown_path: str = Field(default="", description="沙盒落盘路径")


class PublishResultOut(BaseModel):
    """发布结果(飞书云文档)."""

    run_id: str
    published: bool = Field(description="是否发布成功")
    doc_url: str = Field(default="", description="飞书云文档链接")
    message: str = Field(default="", description="可读结果/降级提示")

"""工具与 Skill Schema - 工具元信息/Skill 信息/执行域.

M3 仅定义 Schema 与路由占位, 工具治理在 P6(M5) 实现.
对齐 core/constants.py: ExecutionDomain(direct/skill_only/subagent_only/internal).
"""

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """工具元信息."""

    name: str
    description: str
    domain: str = Field(description="执行域: direct/skill_only/subagent_only/internal")
    enabled: bool = True


class SkillInfo(BaseModel):
    """Skill 元信息(来自 SKILL.md frontmatter)."""

    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    domain: str = "skill_only"
    enabled: bool = True


class SkillToggleResponse(BaseModel):
    """Skill 启停响应."""

    name: str
    enabled: bool

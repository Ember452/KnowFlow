"""Skill 定义数据模型 - 来自 SKILL.md 的 YAML frontmatter.

字段对齐设计文档: name / description / tools / dependencies / domain / enabled.
domain 必须是 ExecutionDomain 之一(通常 skill_only).
"""

from pydantic import BaseModel, Field, field_validator

from knowflow.core.constants import ExecutionDomain


class SkillDefinition(BaseModel):
    """Skill 声明式定义(YAML frontmatter 解析结果)."""

    name: str = Field(min_length=1)
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("skill name 不能为空")
        return v

    @field_validator("tools", "dependencies")
    @classmethod
    def _dedup(cls, v: list[str]) -> list[str]:
        # 去重保序
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

"""Skill 端点 - M3 仅占位, 工具治理与 Skill 体系在 P6(M5) 实现."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/skills", tags=["skill"])


@router.get("", status_code=501)
async def list_skills() -> None:
    """Skill 列表. P6(M5) 接 SkillLoader(SKILL.md frontmatter 解析)."""
    raise HTTPException(status_code=501, detail="工具治理与 Skill 体系在 P6(M5) 实现")


@router.put("/{name}/toggle", status_code=501)
async def toggle_skill(name: str) -> None:
    """启用/禁用 Skill. P6(M5) 实现."""
    raise HTTPException(status_code=501, detail="工具治理与 Skill 体系在 P6(M5) 实现")

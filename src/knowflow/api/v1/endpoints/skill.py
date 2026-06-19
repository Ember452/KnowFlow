"""Skill 端点 - 列出/启停 Skill(基于 SkillManager 运行时状态).

GET /skills 返回全部 Skill(含 tools/dependencies/domain/enabled).
PUT /skills/{name}/toggle 切换启停状态, 进程内即时生效.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from knowflow.api.deps import get_skill_manager
from knowflow.schemas.tool import SkillInfo, SkillToggleResponse
from knowflow.tools.skill_manager import SkillManager

router = APIRouter(prefix="/skills", tags=["skill"])


@router.get("", response_model=list[SkillInfo])
async def list_skills(
    manager: Annotated[SkillManager, Depends(get_skill_manager)],
) -> list[SkillInfo]:
    """列出全部 Skill(含运行时启停状态)."""
    return manager.list()


@router.put("/{name}/toggle", response_model=SkillToggleResponse)
async def toggle_skill(
    name: str,
    manager: Annotated[SkillManager, Depends(get_skill_manager)],
) -> SkillToggleResponse:
    """切换 Skill 启停状态. 不存在返回 404."""
    return manager.toggle(name)

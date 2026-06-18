"""Skill 管理器 - 加载 SKILL.md 并维护运行时启停状态.

加载目录下全部 Skill 定义, 提供 list/toggle/get_active 接口. 启停状态在内存中维护
(不落库), 进程重启后回到 SKILL.md 声明的 enabled 初值. active_skills() 返回的
SkillDefinition 已同步运行时 enabled, 供可见性计算直接使用.
"""

from pathlib import Path

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import NotFoundError
from knowflow.core.logging import get_logger
from knowflow.schemas.tool import SkillInfo, SkillToggleResponse
from knowflow.tools.skill_loader import SkillLoader
from knowflow.tools.skill_schema import SkillDefinition

logger = get_logger(__name__)


class SkillManager:
    """Skill 运行时管理: 加载定义 + 维护启停状态."""

    def __init__(
        self,
        skills_dir: str | Path | None = None,
        loader: SkillLoader | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._loader = loader or SkillLoader()
        skills_dir = skills_dir or self._settings.skills_dir
        self._defs: list[SkillDefinition] = self._loader.load_dir(skills_dir)
        # 运行时启停状态: 初始取 SKILL.md 的 enabled
        self._enabled: dict[str, bool] = {s.name: s.enabled for s in self._defs}
        logger.info("skills.loaded", count=len(self._defs), dir=str(skills_dir))

    def get(self, name: str) -> SkillDefinition | None:
        for s in self._defs:
            if s.name == name:
                return s
        return None

    def active_skills(self) -> list[SkillDefinition]:
        """返回当前启用的 Skill(已同步运行时 enabled, 供可见性计算)."""
        result: list[SkillDefinition] = []
        for s in self._defs:
            if self._enabled.get(s.name, s.enabled):
                # 同步运行时 enabled 到返回实例, 避免可见性计算读到旧值
                result.append(s.model_copy(update={"enabled": True}))
        return result

    def toggle(self, name: str) -> SkillToggleResponse:
        """切换 Skill 启停; 返回新状态. 不存在抛 NotFoundError."""
        if name not in self._enabled:
            raise NotFoundError(f"Skill 不存在: {name}")
        self._enabled[name] = not self._enabled[name]
        logger.info("skills.toggled", skill=name, enabled=self._enabled[name])
        return SkillToggleResponse(name=name, enabled=self._enabled[name])

    # NOTE: list 方法须放在所有使用 list[...] 标注的方法之后, 否则类体内 `list`
    # 名称被本方法遮蔽, 导致其上方方法的返回标注 list[...] 报错.
    def list(self) -> list[SkillInfo]:
        """列出全部 Skill(含运行时启停状态)."""
        return [
            SkillInfo(
                name=s.name,
                description=s.description,
                tools=list(s.tools),
                dependencies=list(s.dependencies),
                domain=s.domain.value,
                enabled=self._enabled.get(s.name, s.enabled),
            )
            for s in self._defs
        ]

    def __len__(self) -> int:
        return len(self._defs)

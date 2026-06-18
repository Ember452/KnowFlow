"""Skill 加载器 - 解析 SKILL.md 的 YAML frontmatter, 构建 SkillDefinition.

格式: 文件首部 --- 包裹的 YAML frontmatter, 之后为 Markdown 正文(忽略).
加载目录下所有 SKILL.md, 校验元信息完整性后返回 SkillDefinition 列表.
"""

from pathlib import Path
from typing import Any

import yaml

from knowflow.core.exceptions import ValidationError
from knowflow.core.logging import get_logger
from knowflow.tools.skill_schema import SkillDefinition

logger = get_logger(__name__)

SKILL_FILE = "SKILL.md"
_FRONTMATTER_DELIM = "---"


class SkillLoader:
    """从文件系统加载 Skill 定义."""

    def load_dir(self, skills_dir: str | Path) -> list[SkillDefinition]:
        """加载目录下每个子目录的 SKILL.md. 单个失败不阻塞其余(记录警告)."""
        root = Path(skills_dir)
        if not root.is_dir():
            raise ValidationError(f"skills 目录不存在: {skills_dir}")
        skills: list[SkillDefinition] = []
        for skill_file in sorted(root.glob(f"*/{SKILL_FILE}")):
            try:
                skills.append(self.load(skill_file))
            except Exception as exc:
                logger.warning("skills.load_failed", file=str(skill_file), error=str(exc))
        return skills

    def load(self, skill_file: str | Path) -> SkillDefinition:
        """解析单个 SKILL.md 的 frontmatter → SkillDefinition."""
        path = Path(skill_file)
        text = path.read_text(encoding="utf-8")
        raw = self._parse_frontmatter(text)
        skill = SkillDefinition(**raw)
        self.validate(skill)
        return skill

    def _parse_frontmatter(self, text: str) -> dict[str, Any]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
            raise ValidationError("SKILL.md 必须以 YAML frontmatter(---) 开头")
        # 找闭合 ---
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == _FRONTMATTER_DELIM:
                end = i
                break
        if end is None:
            raise ValidationError("SKILL.md frontmatter 未闭合(缺少结尾 ---)")
        body = "\n".join(lines[1:end])
        try:
            data = yaml.safe_load(body) or {}
        except yaml.YAMLError as exc:
            raise ValidationError(f"SKILL.md YAML 解析失败: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError("SKILL.md frontmatter 必须是 YAML 字典")
        return data

    def validate(self, skill: SkillDefinition) -> None:
        """校验元信息完整性. name 必填; tools 与 dependencies 中的工具名需合法."""
        if not skill.name:
            raise ValidationError("skill name 不能为空")
        # 工具名仅允许字母/数字/下划线
        for t in [*skill.tools, *skill.dependencies]:
            if not t.replace("_", "").isalnum():
                raise ValidationError(f"非法工具名: {t}")

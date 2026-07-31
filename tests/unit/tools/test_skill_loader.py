"""Skill 加载器与定义模型单测 - YAML frontmatter 解析/校验/目录加载.

SkillLoader 解析 SKILL.md 的 frontmatter → SkillDefinition; 校验 name 必填、
工具名合法. load_dir 单个失败不阻塞其余.
"""

from pathlib import Path

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import ValidationError
from knowflow.tools.skill_loader import SkillLoader
from knowflow.tools.skill_schema import SkillDefinition

# ── SkillDefinition 模型 ──


def test_skill_definition_defaults() -> None:
    """默认 domain=skill_only, enabled=True, tools/dependencies 为空."""
    s = SkillDefinition(name="qa")
    assert s.domain == ExecutionDomain.SKILL_ONLY
    assert s.enabled is True
    assert s.tools == []
    assert s.dependencies == []


def test_skill_definition_name_normalized() -> None:
    """name 被去空白."""
    s = SkillDefinition(name="  qa  ")
    assert s.name == "qa"


def test_skill_definition_name_empty_raises() -> None:
    """空 name 校验失败."""
    with pytest.raises(ValueError):
        SkillDefinition(name="   ")


def test_skill_definition_dedup_tools() -> None:
    """tools 去重保序."""
    s = SkillDefinition(name="s", tools=["a", "b", "a", "c"])
    assert s.tools == ["a", "b", "c"]


def test_skill_definition_dedup_dependencies() -> None:
    """dependencies 去重保序."""
    s = SkillDefinition(name="s", dependencies=["x", "x", "y"])
    assert s.dependencies == ["x", "y"]


# ── SkillLoader 单文件解析 ──


def _write_skill(tmp_path: Path, name: str, content: str = "") -> Path:
    """在 tmp_path/name/ 下写 SKILL.md, 返回文件路径."""
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def test_load_valid_skill(tmp_path: Path) -> None:
    """合法 frontmatter 解析为 SkillDefinition."""
    skill_file = _write_skill(
        tmp_path,
        "qa",
        "---\n"
        "name: qa\n"
        "description: 问答\n"
        "tools:\n"
        "  - retrieval_tool\n"
        "domain: skill_only\n"
        "enabled: true\n"
        "---\n# 正文\n",
    )
    skill = SkillLoader().load(skill_file)
    assert skill.name == "qa"
    assert skill.description == "问答"
    assert skill.tools == ["retrieval_tool"]
    assert skill.domain == ExecutionDomain.SKILL_ONLY
    assert skill.enabled is True


def test_load_missing_frontmatter_delim(tmp_path: Path) -> None:
    """无 frontmatter 起始 --- 抛 ValidationError."""
    skill_file = _write_skill(tmp_path, "bad", "name: bad\n")
    with pytest.raises(ValidationError, match="frontmatter"):
        SkillLoader().load(skill_file)


def test_load_unclosed_frontmatter(tmp_path: Path) -> None:
    """frontmatter 未闭合抛 ValidationError."""
    skill_file = _write_skill(tmp_path, "bad", "---\nname: bad\n")
    with pytest.raises(ValidationError, match="未闭合"):
        SkillLoader().load(skill_file)


def test_load_invalid_yaml(tmp_path: Path) -> None:
    """YAML 语法错误抛 ValidationError."""
    skill_file = _write_skill(tmp_path, "bad", "---\nname: [unclosed\n---\n")
    with pytest.raises(ValidationError, match="YAML"):
        SkillLoader().load(skill_file)


def test_load_non_dict_frontmatter(tmp_path: Path) -> None:
    """frontmatter 为非字典(列表)抛 ValidationError."""
    skill_file = _write_skill(tmp_path, "bad", "---\n- a\n- b\n---\n")
    with pytest.raises(ValidationError, match="字典"):
        SkillLoader().load(skill_file)


def test_load_illegal_tool_name(tmp_path: Path) -> None:
    """工具名含非法字符抛 ValidationError."""
    skill_file = _write_skill(tmp_path, "bad", "---\nname: bad\ntools:\n  - 'tool-name!'\n---\n")
    with pytest.raises(ValidationError, match="非法工具名"):
        SkillLoader().load(skill_file)


# ── SkillLoader 目录加载 ──


def test_load_dir_multiple_skills(tmp_path: Path) -> None:
    """加载目录下多个 Skill, 按子目录名排序."""
    _write_skill(tmp_path, "qa", "---\nname: qa\ntools:\n  - retrieval_tool\n---\n# qa\n")
    _write_skill(tmp_path, "data", "---\nname: data\ntools:\n  - calculator\n---\n# data\n")
    skills = SkillLoader().load_dir(tmp_path)
    assert len(skills) == 2
    assert {s.name for s in skills} == {"qa", "data"}


def test_load_dir_skips_invalid_one(tmp_path: Path) -> None:
    """单个 Skill 解析失败不阻塞其余, 仅记 warning."""
    _write_skill(tmp_path, "good", "---\nname: good\n---\n# good\n")
    _write_skill(tmp_path, "bad", "no frontmatter here")
    skills = SkillLoader().load_dir(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "good"


def test_load_dir_not_exists_raises() -> None:
    """目录不存在抛 ValidationError."""
    with pytest.raises(ValidationError, match="不存在"):
        SkillLoader().load_dir("/nonexistent/path/xyz")


def test_load_dir_empty(tmp_path: Path) -> None:
    """空目录返回空列表."""
    assert SkillLoader().load_dir(tmp_path) == []


def test_load_dir_real_skills() -> None:
    """加载项目真实 skills/ 目录的 6 个 SKILL.md."""
    skills = SkillLoader().load_dir("skills")
    assert len(skills) == 6
    names = {s.name for s in skills}
    expected = {
        "knowledge_qa",
        "document_summary",
        "data_analysis",
        "code_review",
        "report_writing",
    }
    assert expected <= names
    # 全部默认 enabled
    assert all(s.enabled for s in skills)

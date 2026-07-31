"""Skill 管理器单测 - 加载/启停/激活列表.

SkillManager 从 skills/ 加载定义, 维护运行时 enabled 状态(内存, 不落库).
active_skills() 同步运行时 enabled 到返回实例, 供可见性计算直接使用.
"""

from pathlib import Path

import pytest

from knowflow.core.exceptions import NotFoundError
from knowflow.tools.skill_manager import SkillManager


@pytest.fixture
def manager() -> SkillManager:
    """加载项目真实 skills/ 目录的 SkillManager."""
    return SkillManager()


# ── 加载 ──


def test_loads_four_skills(manager: SkillManager) -> None:
    """项目 skills/ 下有 6 个 Skill."""
    assert len(manager) == 6


def test_get_existing(manager: SkillManager) -> None:
    """get 返回已加载的 SkillDefinition."""
    skill = manager.get("knowledge_qa")
    assert skill is not None
    assert skill.name == "knowledge_qa"
    assert "retrieval_tool" in skill.tools


def test_get_missing_returns_none(manager: SkillManager) -> None:
    """get 未加载的 Skill 返回 None."""
    assert manager.get("nonexistent") is None


# ── list ──


def test_list_returns_all(manager: SkillManager) -> None:
    """list 返回全部 Skill 的 SkillInfo."""
    infos = manager.list()
    assert len(infos) == 6
    names = {i.name for i in infos}
    expected = {
        "knowledge_qa",
        "document_summary",
        "data_analysis",
        "code_review",
        "report_writing",
        "report_publish",
    }
    assert expected <= names
    # 初始全部 enabled
    assert all(i.enabled for i in infos)


def test_list_info_fields(manager: SkillManager) -> None:
    """SkillInfo 含 tools/dependencies/domain/enabled."""
    infos = {i.name: i for i in manager.list()}
    qa = infos["knowledge_qa"]
    assert qa.tools == ["retrieval_tool"]
    assert qa.domain == "skill_only"
    assert qa.enabled is True
    # code_review 为 subagent_only 域
    assert infos["code_review"].domain == "subagent_only"


# ── toggle ──


def test_toggle_disables(manager: SkillManager) -> None:
    """toggle 切换 enabled 状态: True → False."""
    resp = manager.toggle("knowledge_qa")
    assert resp.enabled is False
    # list 中反映新状态
    infos = {i.name: i for i in manager.list()}
    assert infos["knowledge_qa"].enabled is False


def test_toggle_reenables(manager: SkillManager) -> None:
    """再次 toggle 恢复 enabled."""
    manager.toggle("data_analysis")
    resp = manager.toggle("data_analysis")
    assert resp.enabled is True


def test_toggle_missing_raises(manager: SkillManager) -> None:
    """toggle 不存在的 Skill 抛 NotFoundError."""
    with pytest.raises(NotFoundError):
        manager.toggle("ghost")


# ── active_skills ──


def test_active_skills_excludes_disabled(manager: SkillManager) -> None:
    """disabled 的 Skill 不在 active_skills 中."""
    manager.toggle("knowledge_qa")
    active = manager.active_skills()
    names = {s.name for s in active}
    assert "knowledge_qa" not in names
    assert len(active) == 5


def test_active_skills_syncs_enabled_flag(manager: SkillManager) -> None:
    """active_skills 返回的 SkillDefinition.enabled 恒为 True."""
    active = manager.active_skills()
    assert all(s.enabled for s in active)


def test_active_skills_returns_copies(manager: SkillManager) -> None:
    """active_skills 返回 model_copy, 修改不影响原定义."""
    active = manager.active_skills()
    assert active  # 非空
    # 返回的是副本, 不会影响 manager 内部状态
    assert len(manager.active_skills()) == len(active)


# ── 自定义加载目录 ──


def test_loads_from_custom_dir(tmp_path: Path) -> None:
    """可指定自定义 skills 目录."""

    skill_dir = tmp_path / "custom"
    skill_dir.mkdir()
    (skill_dir / "my_skill").mkdir()
    (skill_dir / "my_skill" / "SKILL.md").write_text(
        "---\nname: my_skill\ntools:\n  - calc\n---\n# my\n", encoding="utf-8"
    )
    mgr = SkillManager(skills_dir=skill_dir)
    assert len(mgr) == 1
    assert mgr.get("my_skill") is not None

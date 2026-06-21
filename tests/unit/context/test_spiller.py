"""卸载器单测 - 超阈值写入沙盒并以引用替换."""

from knowflow.context.spiller import Spiller
from knowflow.context.token_counter import TokenCounter
from knowflow.core.config import Settings
from knowflow.sandbox.workspace import WorkspaceManager
from tests.fakes import FakeMinio

# 用未知模型强制字符回退: token ≈ 字符/4
_SETTINGS = Settings(llm_model="__unknown_model__", spill_threshold_tokens=100)


def _spiller() -> tuple[Spiller, FakeMinio]:
    """返回 (spiller, 共享的 FakeMinio 实例), 便于读回验证同一存储."""
    minio = FakeMinio()
    return (
        Spiller(
            workspace_manager=WorkspaceManager(minio),
            settings=_SETTINGS,
            counter=TokenCounter(settings=_SETTINGS),
        ),
        minio,
    )


async def test_spill_when_exceeds_threshold() -> None:
    """超阈值文本写入沙盒 /workspace/spilled/, 返回引用."""
    spiller, minio = _spiller()
    long_text = "报销流程" * 200  # 800 字符 → 200 token > 100
    result = await spiller.spill_if_needed(long_text, session_id="42")

    assert result.spilled is True
    assert result.path is not None
    assert result.path.startswith("/workspace/spilled/")
    assert '"spilled": true' in result.reference()
    assert result.path in result.reference()
    # 原文可通过沙盒读回(同一存储)
    content = await WorkspaceManager(minio).for_session("42").read(result.path)
    assert content.decode("utf-8") == long_text


async def test_no_spill_within_threshold() -> None:
    """未超阈值原样返回, 不写沙盒."""
    spiller, minio = _spiller()
    short_text = "报销流程是什么"
    result = await spiller.spill_if_needed(short_text, session_id="42")

    assert result.spilled is False
    assert result.text == short_text
    assert result.path is None
    assert await WorkspaceManager(minio).for_session("42").list() == []


async def test_empty_text_never_spills() -> None:
    spiller, _ = _spiller()
    result = await spiller.spill_if_needed("", session_id="1")
    assert result.spilled is False

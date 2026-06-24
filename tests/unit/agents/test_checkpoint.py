"""CheckpointManager 单测 - 序列化/恢复/lineage(注入 InMemorySaver, 不依赖 PG)."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from knowflow.agents.checkpoint import CheckpointManager


@pytest.fixture
def manager() -> CheckpointManager:
    """注入 InMemorySaver 的 CheckpointManager."""
    return CheckpointManager(saver=InMemorySaver())


@pytest.mark.asyncio
async def test_save_and_restore_roundtrip(manager: CheckpointManager) -> None:
    """save 后 restore 能取回相同状态."""
    state = {"query": "对比三款产品", "needs_delegation": True, "plan": [{"id": "t1"}]}
    ckpt_id = await manager.save(state, "run-1", metadata={"node": "plan"})
    restored = await manager.restore("run-1", ckpt_id)
    assert restored is not None
    assert restored["query"] == "对比三款产品"
    assert restored["needs_delegation"] is True
    assert restored["plan"] == [{"id": "t1"}]


@pytest.mark.asyncio
async def test_restore_latest_when_no_checkpoint_id(manager: CheckpointManager) -> None:
    """不指定 checkpoint_id 时恢复线程最新状态."""
    await manager.save({"step": 1}, "run-1")
    await manager.save({"step": 2}, "run-1")
    restored = await manager.restore("run-1")
    assert restored == {"step": 2}


@pytest.mark.asyncio
async def test_restore_missing_returns_none(manager: CheckpointManager) -> None:
    """不存在的线程/checkpoint 返回 None."""
    assert await manager.restore("not-exists") is None


@pytest.mark.asyncio
async def test_lineage_walks_up(manager: CheckpointManager) -> None:
    """lineage 从当前向根回溯, 顺序 [leaf, ..., root], 原生 parent 自动维护."""
    ckpt1 = await manager.save({"step": 1}, "run-1")
    ckpt2 = await manager.save({"step": 2}, "run-1")
    ckpt3 = await manager.save({"step": 3}, "run-1")

    chain = await manager.lineage("run-1", ckpt3)
    ids = [c["checkpoint_id"] for c in chain]
    assert ids == [ckpt3, ckpt2, ckpt1]
    assert chain[0]["parent_checkpoint_id"] == ckpt2
    assert chain[-1]["parent_checkpoint_id"] is None
    assert chain[0]["state"]["step"] == 3


@pytest.mark.asyncio
async def test_lineage_latest_without_id(manager: CheckpointManager) -> None:
    """不指定 checkpoint_id 时从线程最新开始回溯."""
    await manager.save({"step": 1}, "run-1")
    await manager.save({"step": 2}, "run-1")
    chain = await manager.lineage("run-1")
    assert [c["state"]["step"] for c in chain] == [2, 1]


@pytest.mark.asyncio
async def test_lineage_missing(manager: CheckpointManager) -> None:
    """不存在的 checkpoint 返回空链路."""
    assert await manager.lineage("run-1", "not-exists") == []


@pytest.mark.asyncio
async def test_save_metadata_roundtrip(manager: CheckpointManager) -> None:
    """metadata(run_id/节点名)随 checkpoint 保存并可在线路中读到."""
    ckpt_id = await manager.save({"step": 1}, "run-9", metadata={"node": "execute", "run_id": 9})
    chain = await manager.lineage("run-9", ckpt_id)
    assert chain[0]["metadata"]["node"] == "execute"
    assert chain[0]["metadata"]["run_id"] == 9


@pytest.mark.asyncio
async def test_threads_isolated(manager: CheckpointManager) -> None:
    """不同线程的 checkpoint 互不干扰."""
    await manager.save({"step": 1}, "run-a")
    await manager.save({"step": 2}, "run-b")
    assert (await manager.restore("run-a")) == {"step": 1}
    assert (await manager.restore("run-b")) == {"step": 2}

"""EvalDataset / EvalRunner 单测 - 加载校验与三类评测流程."""

import json

import pytest

from knowflow.observability.eval.dataset import EvalDataset, EvalItem
from knowflow.observability.eval.runner import EvalRunner


class FakeChunk:
    """fake 检索 chunk."""

    def __init__(self, chunk_id: int, content: str) -> None:
        self.chunk_id = chunk_id
        self.content = content


class FakeRetriever:
    """脚本化 retriever: 按 query 返回固定 chunk 序列."""

    def __init__(self, mapping: dict[str, list[FakeChunk]]) -> None:
        self._mapping = mapping
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, query: str, top_k: int = 10) -> object:
        self.calls.append((query, top_k))
        return type("R", (), {"query": query, "chunks": self._mapping.get(query, [])[:top_k]})()


class FakeLLM:
    """脚本化 LLM: 按 query 返回固定答案."""

    def __init__(self, answers: dict[str, str]) -> None:
        self._answers = answers
        self.calls: list[object] = []

    async def ainvoke(self, messages: object) -> str:
        self.calls.append(messages)
        user = next(m["content"] for m in messages if m["role"] == "user")
        return self._answers.get(user, "默认答案")


def _write_dataset(tmp_path, lines: list[dict], kind: str) -> str:
    path = tmp_path / f"{kind}.jsonl"
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8")
    return str(path)


# ── dataset 加载/校验 ──


def test_dataset_load_retrieval(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """retrieval 格式加载: query/doc_ids/category."""
    path = _write_dataset(
        tmp_path,
        [{"query": "年假几天", "doc_ids": [1], "category": "direct"}],
        "retrieval",
    )
    ds = EvalDataset.load(path, kind="retrieval")
    assert ds.name == "retrieval"
    assert ds.items[0].doc_ids == [1]
    assert ds.items[0].category == "direct"


def test_dataset_load_qa(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """knowledge_qa 格式加载: query/answer_keypoints/related_chunks."""
    path = _write_dataset(
        tmp_path,
        [
            {
                "query": "报销流程",
                "answer_keypoints": ["填写报销单", "部门审批"],
                "related_chunks": [1, 2],
            }
        ],
        "qa",
    )
    ds = EvalDataset.load(path, kind="knowledge_qa")
    assert ds.items[0].answer_keypoints == ["填写报销单", "部门审批"]
    assert ds.items[0].related_chunks == [1, 2]


def test_dataset_rejects_missing_fields(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """缺少必需字段时抛 ValueError(行号可定位)."""
    path = _write_dataset(tmp_path, [{"query": ""}], "retrieval")
    with pytest.raises(ValueError, match="缺少 query"):
        EvalDataset.load(path, kind="retrieval")

    path2 = _write_dataset(tmp_path, [{"query": "q"}], "retrieval")
    with pytest.raises(ValueError, match="缺少 doc_ids"):
        EvalDataset.load(path2, kind="retrieval")


def test_dataset_rejects_invalid_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """JSON 解析失败抛 ValueError."""
    path = tmp_path / "bad.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON 解析失败"):
        EvalDataset.load(path, kind="retrieval")


# ── runner 检索评测 ──


async def test_run_retrieval_with_chunk_map() -> None:
    """chunk_map 存在时按文档级判定 Recall/MRR/NDCG."""
    retriever = FakeRetriever({"年假": [FakeChunk(11, "年假 5 天"), FakeChunk(21, "病假工资")]})
    runner = EvalRunner(retriever, FakeLLM({}), chunk_map={1: [11, 12], 2: [21]})
    ds = EvalDataset("retrieval", [])  # 直接构造 item
    ds.items = [EvalItem(query="年假", doc_ids=[1])]
    result = await runner.run_retrieval(ds, top_k=10)
    assert result["summary"]["recall@10"] == 1.0
    assert result["summary"]["mrr"] == 1.0
    assert result["details"][0]["hit_docs"] == [1]


async def test_run_retrieval_without_chunk_map() -> None:
    """无 chunk_map 时按 chunk id 直接判定."""

    class DirectLLM:
        async def ainvoke(self, messages: object) -> str:
            return ""

    retriever = FakeRetriever({"报销": [FakeChunk(1, "报销流程"), FakeChunk(2, "无关")]})
    runner = EvalRunner(retriever, DirectLLM(), chunk_map=None)
    ds = EvalDataset("retrieval", [])
    ds.items = [EvalItem(query="报销", doc_ids=[])]
    result = await runner.run_retrieval(ds, top_k=10)
    # doc_ids 为空 → 相关为空 → 指标 0(不抛错)
    assert result["summary"]["recall@10"] == 0.0
    assert retriever.calls[0][1] == 10  # top_k 透传


# ── runner QA 评测 ──


async def test_run_qa_keypoint_hit() -> None:
    """QA 评测: LLM 答案按要点命中率计分, 检索上下文注入 prompt."""
    retriever = FakeRetriever({"报销流程": [FakeChunk(1, "报销需填表并提交部门审批")]})
    llm = FakeLLM({"报销流程": "报销需填表并提交部门审批"})
    runner = EvalRunner(retriever, llm)
    ds = EvalDataset("qa", [])
    ds.items = [EvalItem(query="报销流程", answer_keypoints=["填表", "部门审批"])]
    result = await runner.run_qa(ds, top_k=5)
    assert result["summary"]["keypoint_hit_rate"] == 1.0
    assert result["details"][0]["keypoint_count"] == 2
    # 检索上下文确实注入 system prompt
    system = next(m["content"] for m in llm.calls[0] if m["role"] == "system")
    assert "报销需填表并提交部门审批" in system


async def test_run_qa_partial_hit() -> None:
    """部分要点命中: 0 < rate < 1."""
    retriever = FakeRetriever({"报销流程": [FakeChunk(1, "报销需填表")]})
    llm = FakeLLM({"报销流程": "报销需填表"})
    runner = EvalRunner(retriever, llm)
    ds = EvalDataset("qa", [])
    ds.items = [EvalItem(query="报销流程", answer_keypoints=["填表", "部门审批"])]
    result = await runner.run_qa(ds)
    assert result["summary"]["keypoint_hit_rate"] == 0.5


def test_run_tool_fc() -> None:
    """工具调用准确率静态评测."""
    result = EvalRunner.run_tool_fc(
        predicted_calls=[["retrieval"], ["retrieval", "calculator"]],
        expected_calls=[["retrieval"], ["retrieval", "calculator"]],
    )
    assert result["fc_accuracy"] == 1.0
    assert result["samples"] == 2


def test_load_chunk_map(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """chunk_id_map.json 加载: 字符串 key 转 int."""
    path = tmp_path / "map.json"
    path.write_text('{"1": [1, 2], "2": [3]}', encoding="utf-8")
    assert EvalRunner.load_chunk_map(path) == {1: [1, 2], 2: [3]}

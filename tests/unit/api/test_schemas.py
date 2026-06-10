"""schemas 序列化与默认值单测."""

from knowflow.schemas.chat import ChatRequest, Citation
from knowflow.schemas.common import ApiResponse, PageResponse
from knowflow.schemas.document import DocumentInfo, UploadResponse
from knowflow.schemas.knowledge import SearchRequest, SearchResponse


def test_api_response_envelope() -> None:
    """统一响应信封默认 code/message 为 ok."""
    r = ApiResponse(data={"x": 1})
    assert r.code == "ok"
    assert r.message == "ok"
    assert r.data == {"x": 1}


def test_page_response_defaults() -> None:
    """分页响应默认空列表."""
    p = PageResponse[int]()
    assert p.items == []
    assert p.total == 0
    assert p.limit == 50


def test_search_request_validation() -> None:
    """检索请求 top_k 范围校验."""
    req = SearchRequest(query="测试", top_k=5)
    assert req.with_expand is True
    assert req.with_rerank is True
    assert req.top_k == 5


def test_search_response() -> None:
    """检索响应 total 与 chunks 长度一致."""
    r = SearchResponse(query="q", chunks=[], total=0, latency_ms=12.3, cache_hit=True)
    assert r.cache_hit is True
    assert r.total == 0


def test_upload_response() -> None:
    """上传响应 duplicated 默认 False."""
    r = UploadResponse(doc_id=1, title="t", status="pending")
    assert r.duplicated is False
    assert r.status == "pending"


def test_document_info_optional_fields() -> None:
    """DocumentInfo 可选字段缺省."""
    info = DocumentInfo(id=1, title="t", file_type="md", status="ready", size_bytes=10)
    assert info.content_hash is None
    assert info.error_message is None


def test_chat_request_defaults() -> None:
    """对话请求 stream 默认 False."""
    req = ChatRequest(message="hi")
    assert req.stream is False
    assert req.session_id is None


def test_citation_optional() -> None:
    """引用仅 chunk_id 必填."""
    c = Citation(chunk_id=1)
    assert c.content is None
    assert c.score is None

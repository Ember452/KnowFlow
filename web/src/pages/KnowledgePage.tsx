/**
 * 知识库: 文档上传(拖拽)/列表/删除/重建索引 + 检索测试(混合检索 → 精排).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteDocument,
  listDocuments,
  reindexDocument,
  searchKnowledge,
  uploadDocument,
} from "../api/endpoints";
import { Card, EmptyState, ErrorAlert, IconButton, PageHeader, Spinner, StatusBadge } from "../components/common";
import { Icon } from "../components/icons";
import type { ChunkResult, DocumentInfo, PageResponse } from "../types/api";

const EXAMPLE_QUERIES = ["报销制度", "差旅标准", "产品对比"];

function SearchTester() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [withRerank, setWithRerank] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ chunks: ChunkResult[]; latency_ms: number; cache_hit: boolean } | null>(null);

  const run = async (text?: string) => {
    const q = (text ?? query).trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await searchKnowledge({ query: q, top_k: topK, with_rerank: withRerank });
      setResult({ chunks: resp.chunks, latency_ms: resp.latency_ms, cache_hit: resp.cache_hit });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="检索测试">
      <div className="mb-2 flex flex-wrap gap-1.5">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => run(q)}
            disabled={loading}
            className="rounded-full border border-gray-200 bg-surface px-2.5 py-1 text-xs text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-600 disabled:opacity-50 dark:hover:border-blue-500 dark:hover:text-blue-400"
          >
            {q}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && run()}
          placeholder="输入检索词…"
          className="h-9 min-w-40 flex-1 rounded-lg border border-gray-300 px-3 text-sm outline-none focus:border-blue-500"
        />
        <select
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="h-9 rounded-lg border border-gray-300 px-2 text-sm"
          title="返回条数"
        >
          {[5, 10, 20, 50].map((n) => (
            <option key={n} value={n}>
              top {n}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input type="checkbox" checked={withRerank} onChange={(e) => setWithRerank(e.target.checked)} />
          精排
        </label>
        <button
          onClick={() => run()}
          disabled={loading || !query.trim()}
          className="h-9 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "检索中…" : "检索"}
        </button>
      </div>
      {error && <div className="mt-2"><ErrorAlert message={error} /></div>}
      {result && (
        <div className="mt-3">
          <div className="mb-2 flex items-center gap-2 text-xs text-gray-500">
            <span>命中 {result.chunks.length} 条</span>
            <span>· {result.latency_ms.toFixed(1)} ms</span>
            {result.cache_hit && <StatusBadge status="ok" />}
            {result.cache_hit && <span>缓存命中</span>}
          </div>
          <div className="max-h-80 space-y-2 overflow-auto">
            {result.chunks.map((c, i) => (
              <div key={c.chunk_id} className="rounded-lg border border-gray-200 bg-gray-50 p-2.5">
                <div className="mb-1 flex items-center gap-2 text-[10px] text-gray-500">
                  <span className="font-bold text-blue-600 dark:text-blue-400">#{i + 1}</span>
                  <span>{c.doc_title ?? `文档 #${c.doc_id ?? "-"}`}</span>
                  <span>score {c.score.toFixed(3)}</span>
                  <span>{c.source}</span>
                </div>
                <div className="line-clamp-3 text-xs text-gray-600">{c.content}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const resp: PageResponse<DocumentInfo> = await listDocuments();
      setDocs(resp.items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  const upload = async (file: File) => {
    setUploading(true);
    setUploadMsg(null);
    setError(null);
    try {
      const resp = await uploadDocument(file);
      setUploadMsg(resp.duplicated ? `已秒传去重: ${resp.title}` : `${resp.title} 已上传, 等待索引`);
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const remove = async (docId: number) => {
    try {
      await deleteDocument(docId);
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const reindex = async (docId: number) => {
    try {
      await reindexDocument(docId);
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const formatSize = (bytes: number) =>
    bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader title="知识库" desc="文档上传、索引管理与混合检索测试" />
      <div className="grid grid-cols-2 gap-4">
        {/* 上传区 */}
        <Card title="上传文档" actions={<span className="text-[10px] text-gray-400">pdf / docx / md / txt ≤ 50MB</span>}>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) void upload(file);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`flex h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed transition-colors ${
              dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
            }`}
          >
            <Icon name="upload" className="h-6 w-6 text-gray-300" />
            <div className="text-sm text-gray-500">{uploading ? "上传中…" : "点击或拖拽文件到此处上传"}</div>
            <div className="text-[10px] text-gray-400">上传后自动分块并建立索引</div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.md,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
              e.target.value = "";
            }}
          />
          {uploadMsg && <div className="mt-2 rounded-lg border border-green-200 bg-green-50 px-3 py-1.5 text-xs text-green-700">{uploadMsg}</div>}
          {error && <div className="mt-2"><ErrorAlert message={error} /></div>}
        </Card>
        <SearchTester />
      </div>

      {/* 文档列表 */}
      <Card
        title={`文档列表 (${docs.length})`}
        className="min-h-0 flex-1"
        actions={
          <IconButton onClick={() => void refresh()} title="刷新">
            <Icon name="refresh" className="h-4 w-4" />
          </IconButton>
        }
      >
        {loading && docs.length === 0 ? (
          <Spinner text="加载文档…" />
        ) : docs.length === 0 ? (
          <EmptyState text="暂无文档" hint="上传文档后自动建立索引(状态 5 秒自动刷新)" />
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-400">
                  <th className="pb-2 pr-2 font-medium">标题</th>
                  <th className="pb-2 pr-2 font-medium">类型</th>
                  <th className="pb-2 pr-2 font-medium">大小</th>
                  <th className="pb-2 pr-2 font-medium">状态</th>
                  <th className="pb-2 pr-2 font-medium">更新时间</th>
                  <th className="pb-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-b border-gray-100 text-gray-600">
                    <td className="max-w-64 truncate py-2 pr-2 font-medium text-gray-800" title={d.title}>
                      {d.title}
                    </td>
                    <td className="py-2 pr-2 text-xs">{d.file_type}</td>
                    <td className="py-2 pr-2 text-xs">{formatSize(d.size_bytes)}</td>
                    <td className="py-2 pr-2">
                      <StatusBadge status={d.status} />
                      {d.error_message && (
                        <span className="ml-1 text-[10px] text-red-500" title={d.error_message}>
                          ⚠
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-2 text-xs">
                      {d.updated_at ? new Date(d.updated_at).toLocaleString() : "-"}
                    </td>
                    <td className="py-2">
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => void reindex(d.id)}
                          className="rounded border border-gray-200 px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                          重建索引
                        </button>
                        <button
                          onClick={() => void remove(d.id)}
                          className="rounded border border-red-200 px-1.5 py-0.5 text-xs text-red-600 hover:bg-red-50 dark:border-red-500/40 dark:text-red-400 dark:hover:bg-red-500/10"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

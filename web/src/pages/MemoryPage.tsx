/**
 * 记忆管理: 长期记忆列表/删除 + 手动沉淀(会话短期记忆 → 长期, 含压缩).
 */

import { useCallback, useEffect, useState } from "react";
import { deleteMemory, listMemory, sedimentMemory } from "../api/endpoints";
import { Card, EmptyState, ErrorAlert, PageHeader, Spinner } from "../components/common";
import { useSession } from "../stores/SessionContext";
import type { MemoryItem } from "../types/api";

function importanceLabel(v: number): string {
  if (v >= 8) return "高";
  if (v >= 5) return "中";
  return "低";
}

function importanceColor(v: number): string {
  if (v >= 8) return "text-red-600 dark:text-red-400";
  if (v >= 5) return "text-amber-600 dark:text-amber-400";
  return "text-gray-500";
}

export default function MemoryPage() {
  const { userId, sessions } = useSession();
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sedimenting, setSedimenting] = useState(false);
  const [sedimentMsg, setSedimentMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listMemory(userId);
      setMemories(items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = async (id: number) => {
    try {
      await deleteMemory(userId, id);
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const sediment = async () => {
    if (sessionId == null) return;
    setSedimenting(true);
    setSedimentMsg(null);
    try {
      const resp = await sedimentMemory(userId, sessionId);
      setSedimentMsg(`沉淀完成, 写入 ${resp.saved} 条长期记忆`);
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSedimenting(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <PageHeader title="记忆管理" desc="长期记忆浏览、删除与手动沉淀" />
      <Card title={`用户 ${userId} 的长期记忆`} actions={<span className="text-[10px] text-gray-400">按重要性 + 时间排序</span>}>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sessionId ?? ""}
            onChange={(e) => setSessionId(e.target.value ? Number(e.target.value) : null)}
            className="h-9 rounded-lg border border-gray-300 px-2 text-sm"
          >
            <option value="">选择会话(手动沉淀来源)</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                会话 #{s.id} {s.title ? `· ${s.title}` : ""}
              </option>
            ))}
          </select>
          <button
            onClick={() => void sediment()}
            disabled={sedimenting || sessionId == null}
            className="h-9 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {sedimenting ? "沉淀中…" : "手动沉淀"}
          </button>
          <span className="text-[10px] text-gray-400">从所选会话提取高价值信息写入长期记忆</span>
          {sedimentMsg && <span className="text-xs text-green-600">{sedimentMsg}</span>}
        </div>
        {error && <div className="mt-2"><ErrorAlert message={error} onRetry={() => void refresh()} /></div>}
      </Card>

      <Card title={`记忆条目 (${memories.length})`} className="min-h-0 flex-1">
        {loading && memories.length === 0 ? (
          <Spinner text="加载记忆…" />
        ) : memories.length === 0 ? (
          <EmptyState text="暂无长期记忆" hint="对话中高价值信息会在沉淀阈值触发时自动写入, 也可手动沉淀" />
        ) : (
          <div className="grid min-h-0 grid-cols-2 gap-3 overflow-auto">
            {memories.map((m) => (
              <div key={m.id} className="flex flex-col rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium ${importanceColor(m.importance)}`}>
                      {importanceLabel(m.importance)} · {m.importance.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-gray-400">会话 #{m.session_id}</span>
                  </div>
                  <button
                    onClick={() => void remove(m.id)}
                    className="rounded border border-red-200 px-1.5 py-0.5 text-[10px] text-red-600 hover:bg-red-50 dark:border-red-500/40 dark:text-red-400 dark:hover:bg-red-500/10"
                  >
                    删除
                  </button>
                </div>
                <div className="line-clamp-4 text-xs leading-relaxed text-gray-700">{m.content}</div>
                {m.summary && (
                  <div className="mt-1.5 border-t border-gray-200 pt-1.5 text-[10px] italic text-gray-400">
                    摘要: {m.summary}
                  </div>
                )}
                {m.last_recall && (
                  <div className="mt-1 text-[10px] text-gray-400">最近召回: {new Date(m.last_recall).toLocaleString()}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
